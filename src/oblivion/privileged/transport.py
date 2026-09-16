"""Moving privileged requests between two processes.

Two transports, with deliberately different honesty about what they provide.

:class:`InProcessTransport` runs the service in the calling process. It is real
- the same service, the same validation, the same MAC - but it provides **no
process isolation whatsoever**, and it says so through its ``isolated``
property. It exists for tests and for development on machines where a privileged
host is not running, and code that cares about isolation can check rather than
assume.

:class:`NamedPipeTransport` is the deployment transport: a Windows named pipe
with an ACL that admits only SYSTEM, Administrators and the account that created
it. The pipe is the trust boundary, so its ACL is a security control and not
configuration - a world-writable pipe would let any local process submit
requests that the service would then dutifully authenticate with its shared key.

Framing is a 4-byte big-endian length followed by UTF-8 JSON, with a hard size
cap. Length-prefixing keeps a slow or hostile peer from desynchronising the
stream, and the cap keeps a declared length from becoming an allocation
primitive.

A note on ctypes
----------------
Every Win32 function used here has its ``argtypes`` and ``restype`` declared
before it is called. This is not tidiness: without a declared signature ctypes
marshals handles as 32-bit ints, which silently truncates them on x64 and makes
calls fail in ways that look like permission problems. The declarations live in
:func:`_declare_signatures`, which is idempotent and called from every entry
point.
"""

from __future__ import annotations

import ctypes
import json
import logging
import struct
import sys
import time
from typing import Any, Final, Protocol, runtime_checkable

from oblivion.privileged.service import PrivilegedService

logger = logging.getLogger(__name__)

DEFAULT_PIPE_NAME: Final = r"\\.\pipe\oblivion-privileged"

#: Hard cap on a single framed message. A privileged request is a few hundred
#: bytes; anything approaching this is malformed or hostile.
MAX_MESSAGE_BYTES: Final = 1024 * 1024

_LENGTH_PREFIX: Final = struct.Struct(">I")

# Win32 constants, named rather than inlined so the calls below read as intent.
_PIPE_ACCESS_DUPLEX: Final = 0x00000003

#: Makes CreateNamedPipeW fail if any instance of the name already exists.
#: Startup-only protection: without it, a pipe squatted before the service
#: starts is silently *joined* (the squatter's DACL and instance limit apply),
#: which was reproduced on Windows. It does nothing for a gap between requests;
#: the persistent instance in :class:`NamedPipeServer` is what closes that.
_FILE_FLAG_FIRST_PIPE_INSTANCE: Final = 0x00080000

#: Byte-stream mode, not message mode. In message mode a read smaller than the
#: message fails with ERROR_MORE_DATA, which makes reading a length prefix and
#: then a body impossible - and the length framing is what protects against a
#: desynchronised or hostile peer, so the framing stays and the mode changes.
_PIPE_TYPE_BYTE: Final = 0x00000000
_PIPE_READMODE_BYTE: Final = 0x00000000
_PIPE_WAIT: Final = 0x00000000
_PIPE_REJECT_REMOTE_CLIENTS: Final = 0x00000008
_GENERIC_READ: Final = 0x80000000
_GENERIC_WRITE: Final = 0x40000000
_OPEN_EXISTING: Final = 3
_TOKEN_QUERY: Final = 0x0008
_TOKEN_USER_CLASS: Final = 1
_SDDL_REVISION_1: Final = 1
_ERROR_FILE_NOT_FOUND: Final = 2
_ERROR_PIPE_BUSY: Final = 231
_ERROR_NO_DATA: Final = 232
_ERROR_PIPE_CONNECTED: Final = 535

#: The pointer-width invalid-handle sentinel. Comparing a HANDLE against a bare
#: ``-1`` never matches on x64, which would make every failed call look like it
#: succeeded - so the sentinel is computed at the same width the API returns.
_INVALID_HANDLE_VALUE: Final = ctypes.c_void_p(-1).value

#: Errors that mean "not yet", rather than "no". A pipe that does not exist yet
#: is the normal condition while the privileged service is starting, and a busy
#: pipe is the normal condition while it is serving another request - so both
#: are worth waiting on rather than failing immediately.
_RETRYABLE_CONNECT_ERRORS: Final = frozenset({_ERROR_FILE_NOT_FOUND, _ERROR_PIPE_BUSY})

#: Only SYSTEM, the local Administrators group, and the creating account may
#: touch the pipe. ``D:P`` makes the DACL protected, so no inherited ACE can
#: widen it later.
_PIPE_SDDL_TEMPLATE: Final = "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;{sid})"

_signatures_declared = False


class TransportError(Exception):
    """Raised when a message could not be exchanged with the service."""


class PipeInstanceError(TransportError):
    """Raised when the server's persistent pipe instance can no longer be used.

    Fatal to the server. It stops rather than closing and recreating the pipe,
    because the moment between close and create is when another process can
    take the name (finding PS-1).
    """


class ServiceUnavailableError(TransportError):
    """Raised when the privileged service cannot be reached at all.

    Distinct from a refusal: unreachable means the pipeline learned nothing
    about the request, whereas a refusal is an answer. Callers must not treat
    the two the same, and the separate type makes that hard to get wrong.
    """


def _declare_signatures() -> None:
    """Declare argtypes/restypes for every Win32 call this module makes.

    Idempotent, and safe to call from any entry point. Undeclared ctypes calls
    marshal handles as 32-bit ints on x64; the resulting truncation produces
    failures that look like access-denied, which is a genuinely misleading thing
    for a security boundary to report.
    """
    global _signatures_declared
    if _signatures_declared or sys.platform != "win32":
        return

    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32

    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []

    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    kernel32.LocalFree.restype = ctypes.c_void_p
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]

    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.GetLastError.argtypes = []

    kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel32.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]

    kernel32.ConnectNamedPipe.restype = wintypes.BOOL
    kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

    kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
    kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]

    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]

    kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]

    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]

    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]

    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]

    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]

    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]

    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]

    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
        wintypes.BOOL
    )
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.ULONG),
    ]

    _signatures_declared = True


@runtime_checkable
class Transport(Protocol):
    """How a client hands an envelope to the service and gets a reply."""

    @property
    def isolated(self) -> bool:
        """Whether this transport actually crosses a process boundary."""
        ...

    def exchange(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Send one request envelope and return the response payload."""
        ...


class InProcessTransport:
    """Calls the service directly. Honest about providing no isolation."""

    def __init__(self, service: PrivilegedService) -> None:
        self._service = service

    @property
    def isolated(self) -> bool:
        return False

    @property
    def service(self) -> PrivilegedService:
        return self._service

    def exchange(self, envelope: dict[str, Any]) -> dict[str, Any]:
        from oblivion.privileged.protocol import PrivilegedRequest, ProtocolError

        # Parsed from the wire dict even in-process, so this path exercises the
        # same strict parser the pipe path does. A transport that skipped
        # parsing would let tests pass against a laxer contract than production.
        try:
            request = PrivilegedRequest.from_wire(envelope.get("request"))
        except ProtocolError as exc:
            raise TransportError(f"Malformed privileged request: {exc}") from None
        return self._service.respond(request, str(envelope.get("mac", "")))


def _encode(payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise TransportError(
            f"Message of {len(body)} bytes exceeds the {MAX_MESSAGE_BYTES}-byte cap"
        )
    return _LENGTH_PREFIX.pack(len(body)) + body


def _decode_length(prefix: bytes) -> int:
    if len(prefix) != _LENGTH_PREFIX.size:
        raise TransportError("Truncated length prefix")
    (length,) = _LENGTH_PREFIX.unpack(prefix)
    if length == 0:
        raise TransportError("Empty message")
    if length > MAX_MESSAGE_BYTES:
        # Refused before allocating: a declared length must never be able to
        # size a buffer on this side.
        raise TransportError(
            f"Declared message length {length} exceeds the {MAX_MESSAGE_BYTES}-byte cap"
        )
    return int(length)


def _read_exactly(handle: int, count: int) -> bytes:
    """Read exactly ``count`` bytes, or fail.

    A byte-stream pipe may return a short read at any point. Treating a short
    read as a complete message is how a framed protocol desynchronises, so this
    loops until the full count arrives and raises if the peer stops early.
    """
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    chunks: list[bytes] = []
    remaining = count

    while remaining > 0:
        buffer = ctypes.create_string_buffer(remaining)
        read = wintypes.DWORD(0)
        if not kernel32.ReadFile(handle, buffer, remaining, ctypes.byref(read), None):
            raise TransportError(
                f"Read failed with error {kernel32.GetLastError()} after "
                f"{count - remaining} of {count} bytes"
            )
        if read.value == 0:
            raise TransportError(
                f"Peer closed after {count - remaining} of {count} bytes"
            )
        chunks.append(buffer.raw[: read.value])
        remaining -= read.value

    return b"".join(chunks)


def _write_all(handle: int, payload: bytes) -> None:
    """Write the whole buffer, or fail."""
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    written = wintypes.DWORD(0)
    if not kernel32.WriteFile(handle, payload, len(payload), ctypes.byref(written), None):
        raise TransportError(f"Write failed with error {kernel32.GetLastError()}")
    if written.value != len(payload):
        raise TransportError(
            f"Short write: {written.value} of {len(payload)} bytes"
        )


def _read_framed(handle: int) -> dict[str, Any]:
    """Read one length-prefixed JSON object."""
    length = _decode_length(_read_exactly(handle, _LENGTH_PREFIX.size))
    body = _read_exactly(handle, length)
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportError(f"Message is not valid JSON: {exc}") from None
    if not isinstance(parsed, dict):
        raise TransportError("Message must be a JSON object")
    return parsed


def current_user_sid() -> str:
    """Return the current process user's SID as a string.

    Used to build the pipe ACL. Raising rather than returning a placeholder
    matters: a failure here must prevent the pipe from being created at all,
    because the alternative is creating it with a weaker ACL than intended.
    """
    if sys.platform != "win32":
        raise TransportError("Named-pipe transport is Windows-only")

    from ctypes import wintypes

    _declare_signatures()
    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
    ):
        raise TransportError("Could not open the process token to determine its SID")

    try:
        size = wintypes.DWORD(0)
        advapi32.GetTokenInformation(
            token, _TOKEN_USER_CLASS, None, 0, ctypes.byref(size)
        )
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(
            token, _TOKEN_USER_CLASS, buffer, size, ctypes.byref(size)
        ):
            raise TransportError("Could not read the process token user")

        class SidAndAttributes(ctypes.Structure):
            _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

        sid_ptr = ctypes.cast(buffer, ctypes.POINTER(SidAndAttributes)).contents.Sid
        sid_string = ctypes.c_wchar_p()
        if not advapi32.ConvertSidToStringSidW(sid_ptr, ctypes.byref(sid_string)):
            raise TransportError("Could not convert the process SID to string form")
        try:
            return str(sid_string.value)
        finally:
            kernel32.LocalFree(ctypes.cast(sid_string, ctypes.c_void_p))
    finally:
        kernel32.CloseHandle(token)


def _build_security_attributes() -> Any:
    """Build SECURITY_ATTRIBUTES carrying the restrictive pipe DACL."""
    from ctypes import wintypes

    _declare_signatures()
    advapi32 = ctypes.windll.advapi32

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", ctypes.c_void_p),
            ("bInheritHandle", wintypes.BOOL),
        ]

    sddl = _PIPE_SDDL_TEMPLATE.format(sid=current_user_sid())
    descriptor = ctypes.c_void_p()
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, _SDDL_REVISION_1, ctypes.byref(descriptor), None
    ):
        raise TransportError(
            "Could not build the pipe security descriptor; refusing to create the "
            "pipe rather than creating it with default permissions"
        )

    attributes = SecurityAttributes()
    attributes.nLength = ctypes.sizeof(SecurityAttributes)
    attributes.lpSecurityDescriptor = descriptor
    attributes.bInheritHandle = False
    # The descriptor is referenced by the structure; keep it alive for as long
    # as the structure is, or the pipe would be created against freed memory.
    attributes._descriptor = descriptor
    return attributes


class NamedPipeServer:
    """Serves privileged requests over a restrictively ACL'd named pipe.

    Single-threaded and one client at a time, on purpose. Privileged filesystem
    operations against a shared target are not obviously safe to run
    concurrently, and serialising them removes a class of race entirely at a
    cost - throughput - that does not matter for this workload.

    **One pipe instance for the life of the server.** The instance is created
    once and reused through ``ConnectNamedPipe``/``DisconnectNamedPipe`` cycles.
    The server never closes and recreates it between requests: while the
    service holds the only instance, another process's ``CreateNamedPipeW`` on
    the name fails with ``ERROR_PIPE_BUSY``, and a close/recreate gap is exactly
    where a local process could take the name (finding PS-1). If the instance
    becomes unusable the server stops instead of recreating it.
    """

    def __init__(
        self,
        service: PrivilegedService,
        pipe_name: str = DEFAULT_PIPE_NAME,
    ) -> None:
        if sys.platform != "win32":
            raise TransportError("Named-pipe transport is Windows-only")
        _declare_signatures()
        self._service = service
        self._pipe_name = pipe_name
        self._stop = False
        self._handle: int | None = None

    @property
    def pipe_name(self) -> str:
        return self._pipe_name

    @property
    def handle(self) -> int | None:
        """The persistent instance, or None when the server is not open."""
        return self._handle

    def stop(self) -> None:
        """Ask the loop to exit. Checked between connections, not mid-request."""
        self._stop = True

    def open(self, timeout_ms: int = 5000) -> int:
        """Create the server's single, persistent pipe instance."""
        if self._handle is not None:
            raise TransportError("The pipe server is already open")
        self._handle = self.create_pipe(timeout_ms)
        return self._handle

    def close(self) -> None:
        """Release the instance. Only for shutdown - it is never recreated."""
        handle, self._handle = self._handle, None
        if handle is not None:
            ctypes.windll.kernel32.CloseHandle(handle)

    def create_pipe(self, timeout_ms: int = 5000) -> int:
        """Create the pipe instance and return its handle.

        Separate from accepting so a caller - notably a test - can know the pipe
        exists before a client tries to connect, instead of racing startup.

        Fails if any instance of the name already exists, so a name squatted
        before startup is reported rather than joined.
        """
        kernel32 = ctypes.windll.kernel32
        attributes = _build_security_attributes()

        handle = kernel32.CreateNamedPipeW(
            self._pipe_name,
            _PIPE_ACCESS_DUPLEX | _FILE_FLAG_FIRST_PIPE_INSTANCE,
            _PIPE_TYPE_BYTE
            | _PIPE_READMODE_BYTE
            | _PIPE_WAIT
            | _PIPE_REJECT_REMOTE_CLIENTS,
            1,
            MAX_MESSAGE_BYTES,
            MAX_MESSAGE_BYTES,
            timeout_ms,
            ctypes.byref(attributes),
        )
        if handle == _INVALID_HANDLE_VALUE or not handle:
            raise TransportError(
                f"CreateNamedPipeW failed with error {kernel32.GetLastError()}"
            )
        return int(handle)

    def accept_once(self, handle: int) -> bool:
        """Answer exactly one request, leaving the instance open for the next.

        Returns False when the client went away before being served. Raises
        :class:`PipeInstanceError` when the instance itself is unusable, and a
        plain :class:`TransportError` when only this exchange failed.
        """
        kernel32 = ctypes.windll.kernel32
        connected = kernel32.ConnectNamedPipe(handle, None)
        if not connected:
            error = kernel32.GetLastError()
            if error == _ERROR_NO_DATA:
                # The client left before being served. The instance still has to
                # be disconnected before it can accept anyone else.
                self._disconnect(handle)
                return False
            if error != _ERROR_PIPE_CONNECTED:
                raise PipeInstanceError(f"ConnectNamedPipe failed with error {error}")

        try:
            try:
                payload = self._read_message(handle)
                reply = InProcessTransport(self._service).exchange(payload)
            except TransportError as exc:
                # A malformed request is answered structurally rather than by
                # dropping the connection, so the caller learns why.
                reply = {
                    "protocol_version": "OBLIVION-PRIV-1",
                    "request_id": "",
                    "operation": "inspect_target",
                    "operation_id": "",
                    "status": "REFUSED",
                    "result": {},
                    "refusals": [str(exc)],
                    "message": "Malformed privileged request",
                }
            self._write_message(handle, reply)
            return True
        finally:
            kernel32.FlushFileBuffers(handle)
            self._disconnect(handle)

    @staticmethod
    def _disconnect(handle: int) -> None:
        kernel32 = ctypes.windll.kernel32
        if not kernel32.DisconnectNamedPipe(handle):
            raise PipeInstanceError(
                f"DisconnectNamedPipe failed with error {kernel32.GetLastError()}"
            )

    def serve_forever(
        self, *, timeout_ms: int = 5000, max_connections: int | None = None
    ) -> None:
        """Serve on one persistent instance until stopped.

        ``max_connections`` bounds the loop for tests and supervised runs. The
        instance is closed only when the loop ends; it is never recreated.
        """
        handle = self._handle if self._handle is not None else self.open(timeout_ms)
        handled = 0
        try:
            while not self._stop and (
                max_connections is None or handled < max_connections
            ):
                handled += 1
                try:
                    self.accept_once(handle)
                except PipeInstanceError:
                    logger.exception("privileged.pipe.instance_unusable")
                    raise
                except TransportError:
                    logger.exception("privileged.pipe.exchange_failed")
        finally:
            self.close()

    def _read_message(self, handle: int) -> dict[str, Any]:
        return _read_framed(handle)

    def _write_message(self, handle: int, payload: dict[str, Any]) -> None:
        _write_all(handle, _encode(payload))


class NamedPipeTransport:
    """Client side of the named pipe. Crosses a real process boundary."""

    def __init__(
        self,
        pipe_name: str = DEFAULT_PIPE_NAME,
        *,
        timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 5.0,
    ) -> None:
        if sys.platform != "win32":
            raise TransportError("Named-pipe transport is Windows-only")
        _declare_signatures()
        self._pipe_name = pipe_name
        self._timeout_seconds = timeout_seconds
        self._connect_timeout_seconds = connect_timeout_seconds

    @property
    def isolated(self) -> bool:
        return True

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    def _connect(self) -> int:
        """Open the pipe, waiting briefly for a service that is starting or busy.

        Without this, a client that races service startup fails with "not
        available" even though the service is milliseconds away from listening,
        and a client arriving mid-request fails even though the pipe is healthy.
        Both are transient, so both are waited on - but only up to a bound,
        because an unbounded wait would turn an absent service into a hang.
        """
        kernel32 = ctypes.windll.kernel32
        deadline = time.monotonic() + self._connect_timeout_seconds

        while True:
            handle = kernel32.CreateFileW(
                self._pipe_name,
                _GENERIC_READ | _GENERIC_WRITE,
                0,
                None,
                _OPEN_EXISTING,
                0,
                None,
            )
            if handle != _INVALID_HANDLE_VALUE and handle:
                return int(handle)

            last_error = kernel32.GetLastError()
            remaining = deadline - time.monotonic()
            if last_error not in _RETRYABLE_CONNECT_ERRORS or remaining <= 0:
                raise ServiceUnavailableError(
                    f"Privileged service pipe {self._pipe_name} is not available "
                    f"(error {last_error})"
                )

            # WaitNamedPipeW returns as soon as an instance is free. It returns
            # false when the pipe does not exist at all, in which case a short
            # sleep before retrying keeps a startup race from spinning.
            if not kernel32.WaitNamedPipeW(self._pipe_name, int(remaining * 1000)):
                time.sleep(min(0.02, max(remaining, 0.0)))

    def exchange(self, envelope: dict[str, Any]) -> dict[str, Any]:
        kernel32 = ctypes.windll.kernel32
        handle = self._connect()
        try:
            _write_all(handle, _encode(envelope))
            return _read_framed(handle)
        finally:
            kernel32.CloseHandle(handle)
