"""The wire contract between the unprivileged API and the privileged service.

This module is the boundary's narrowest point, so it is deliberately the
strictest. Everything crossing it is a *claim* made by a less-trusted process:
nothing here is treated as already validated, and nothing here can name code to
run. Two properties matter most.

**The operation set is closed.** :class:`PrivilegedOperation` is an allowlist. A
request naming anything else does not reach a handler and cannot be coerced into
one by casing, whitespace or aliasing. There is deliberately no
``execute_command``, no ``powershell``, no ``cmd``, and no way to express an
arbitrary executable or script - see ``docs/PRIVILEGE_BOUNDARY.md``.

**Parsing is total and fail-closed.** :meth:`PrivilegedRequest.from_wire` accepts
only the exact field set, with the exact types, plus the parameters the named
operation declares. Unknown fields are a refusal rather than something ignored,
because a field the privileged side silently drops is a field the unprivileged
side may believe is being enforced.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

from oblivion.core.evidence.canonicalize import canonicalize

PROTOCOL_VERSION: Final = "OBLIVION-PRIV-1"


class ProtocolError(Exception):
    """Raised when a payload is not a well-formed privileged message.

    Raised at the parsing boundary, before any handler is selected, so a
    malformed or hostile payload never reaches an operation at all.
    """


class PrivilegedOperation(str, Enum):
    """The complete set of operations the privileged service will perform.

    Sourced from ``docs/PRIVILEGE_BOUNDARY.md``. Adding a member widens the
    privileged attack surface, so each must be a specific filesystem action with
    a validated target - never a general-purpose escape hatch.
    """

    INSPECT_TARGET = "inspect_target"
    DELETE_FILE = "delete_file"
    DELETE_TREE = "delete_tree"
    PREPARE_RECOVERY_OBJECT = "prepare_recovery_object"
    RESTORE_RECOVERY_OBJECT = "restore_recovery_object"
    SCAN_SCOPE = "scan_scope"


class ResponseStatus(str, Enum):
    """How a privileged request concluded.

    ``REFUSED`` and ``FAILED`` stay distinct on purpose: refused means the
    boundary declined and nothing was touched; failed means the operation was
    permitted, attempted, and did not complete. Collapsing the two would make
    "we did nothing" indistinguishable from "we tried and something went wrong",
    which is exactly the distinction an evidence record needs.
    """

    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"


#: Operations that modify the filesystem. Only these require a target identity
#: and a TOCTOU revalidation immediately before the act.
DESTRUCTIVE_OPERATIONS: Final[frozenset[PrivilegedOperation]] = frozenset(
    {
        PrivilegedOperation.DELETE_FILE,
        PrivilegedOperation.DELETE_TREE,
        PrivilegedOperation.PREPARE_RECOVERY_OBJECT,
    }
)

#: Operations that only read. Listed explicitly rather than derived as "not
#: destructive", so adding an operation forces a deliberate choice.
READ_ONLY_OPERATIONS: Final[frozenset[PrivilegedOperation]] = frozenset(
    {
        PrivilegedOperation.INSPECT_TARGET,
        PrivilegedOperation.SCAN_SCOPE,
    }
)

#: Operations that write to a destination rather than destroying a target.
RESTORE_OPERATIONS: Final[frozenset[PrivilegedOperation]] = frozenset(
    {PrivilegedOperation.RESTORE_RECOVERY_OBJECT}
)

#: Additional parameters each operation accepts; an operation absent from this
#: mapping accepts none. Parameters are values - an object id, a destination
#: path - never code, never a command, never a key.
ALLOWED_PARAMS: Final[dict[PrivilegedOperation, frozenset[str]]] = {
    PrivilegedOperation.RESTORE_RECOVERY_OBJECT: frozenset(
        {"object_id", "destination_path"}
    ),
}

#: Parameter names that must never cross the boundary. The privileged service
#: reads its own secrets from its own environment; a request offering key
#: material is either a mistake or an attempt to substitute a vault key, and
#: both are refused rather than sanitized.
FORBIDDEN_PARAM_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"password",
        r"passwd",
        r"secret",
        r"token",
        r"private_?key",
        r"vault_?key",
        r"recovery_?key",
        r"signing_?key",
        r"credential",
        r"api_?key",
        r"dsn",
        r"connection_?string",
    )
)

#: Substrings indicating an attempt to smuggle command execution through a value
#: field. Defence in depth, not the primary control: the primary control is that
#: no handler ever passes a request value to a shell, a subprocess or an
#: interpreter. This exists so such an attempt is visible rather than silent.
_COMMAND_MARKERS: Final[tuple[str, ...]] = (
    "powershell",
    "cmd.exe",
    "&&",
    "||",
    "`",
    "$(",
    "|",
    ">",
    "<",
)

_REQUEST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "protocol_version",
        "request_id",
        "nonce",
        "operation",
        "operation_id",
        "policy_id",
        "mode",
        "target_path",
        "target_type",
        "expected_volume_serial",
        "expected_file_id",
        "actor_id",
        "issued_at",
        "params",
    }
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ProtocolError(f"Field '{key}' must be a string")
    if not value.strip():
        raise ProtocolError(f"Field '{key}' must not be empty")
    return value


def _require_identifier(payload: dict[str, Any], key: str) -> str:
    value = _require_str(payload, key)
    if not _IDENTIFIER.match(value):
        raise ProtocolError(
            f"Field '{key}' is not a well-formed identifier; letters, digits, "
            "dot, underscore, colon and hyphen only"
        )
    return value


def reject_command_markers(label: str, value: str) -> None:
    """Refuse a value that looks like an attempt at command execution.

    Defence in depth. No handler passes a request value to a shell, so a marker
    here cannot by itself achieve execution - but a request containing one is
    not one this system should service, and refusing loudly beats stripping
    quietly.
    """
    lowered = value.lower()
    for marker in _COMMAND_MARKERS:
        if marker in lowered:
            raise ProtocolError(
                f"Field '{label}' contains a command-execution marker ({marker!r}); "
                "the privileged boundary accepts no commands"
            )


@dataclass(frozen=True)
class PrivilegedRequest:
    """A structured request to the privileged service, validated on parse.

    Parsing this successfully means the message is *well-formed*. It does not
    mean the operation is permitted: authorization, policy compatibility, path
    containment and target identity are all decided by the privileged side in
    :mod:`oblivion.privileged.validation`, against its own configuration.
    """

    request_id: str
    nonce: str
    operation: PrivilegedOperation
    operation_id: str
    policy_id: str
    mode: str
    target_path: str
    target_type: str
    actor_id: str
    issued_at: _dt.datetime
    expected_volume_serial: str | None = None
    expected_file_id: tuple[int, int, int] | None = None
    params: dict[str, str] = field(default_factory=dict)
    protocol_version: str = PROTOCOL_VERSION

    def to_wire(self) -> dict[str, Any]:
        """Render to a JSON-compatible dict for transport."""
        return {
            "protocol_version": self.protocol_version,
            "request_id": self.request_id,
            "nonce": self.nonce,
            "operation": self.operation.value,
            "operation_id": self.operation_id,
            "policy_id": self.policy_id,
            "mode": self.mode,
            "target_path": self.target_path,
            "target_type": self.target_type,
            "expected_volume_serial": self.expected_volume_serial,
            "expected_file_id": (
                list(self.expected_file_id) if self.expected_file_id else None
            ),
            "actor_id": self.actor_id,
            "issued_at": self.issued_at.isoformat(),
            "params": dict(self.params),
        }

    def to_bytes(self) -> bytes:
        """Deterministic framing, reusing the Phase 23 canonicalizer.

        One codec for everything that must hash or compare identically keeps a
        privileged request quotable in an evidence record without a second,
        subtly different serializer drifting away from the first. It is also
        what the request MAC is computed over, so framing and integrity cannot
        disagree.
        """
        return canonicalize(self.to_wire())

    @classmethod
    def from_wire(cls, payload: Any) -> PrivilegedRequest:
        """Parse a payload, refusing anything not exactly well-formed.

        Every refusal here raises :class:`ProtocolError` before an operation is
        selected. There is no partial acceptance and no coercion: a request that
        is not understood is not serviced.
        """
        if not isinstance(payload, dict):
            raise ProtocolError("Privileged request must be a JSON object")

        unknown = set(payload) - _REQUEST_FIELDS
        if unknown:
            raise ProtocolError(
                f"Unknown field(s) in privileged request: {sorted(unknown)}. The "
                "privileged boundary rejects fields it would otherwise ignore."
            )

        version = payload.get("protocol_version", PROTOCOL_VERSION)
        if version != PROTOCOL_VERSION:
            raise ProtocolError(
                f"Unsupported protocol version {version!r}; expected {PROTOCOL_VERSION!r}"
            )

        raw_operation = payload.get("operation")
        if not isinstance(raw_operation, str):
            raise ProtocolError("Field 'operation' must be a string")
        try:
            operation = PrivilegedOperation(raw_operation)
        except ValueError:
            raise ProtocolError(
                f"Operation {raw_operation!r} is not in the privileged allowlist. "
                f"Permitted: {sorted(o.value for o in PrivilegedOperation)}"
            ) from None

        target_path = _require_str(payload, "target_path")
        reject_command_markers("target_path", target_path)

        target_type = _require_str(payload, "target_type")
        if target_type not in ("file", "directory"):
            raise ProtocolError(
                f"Field 'target_type' must be 'file' or 'directory', got {target_type!r}"
            )

        raw_serial = payload.get("expected_volume_serial")
        if raw_serial is not None and not isinstance(raw_serial, str):
            raise ProtocolError(
                "Field 'expected_volume_serial' must be a string or null"
            )

        return cls(
            request_id=_require_identifier(payload, "request_id"),
            nonce=_require_identifier(payload, "nonce"),
            operation=operation,
            operation_id=_require_identifier(payload, "operation_id"),
            policy_id=_require_identifier(payload, "policy_id"),
            mode=_require_identifier(payload, "mode"),
            target_path=target_path,
            target_type=target_type,
            actor_id=_require_identifier(payload, "actor_id"),
            issued_at=cls._parse_issued_at(payload.get("issued_at")),
            expected_volume_serial=raw_serial,
            expected_file_id=cls._parse_file_id(payload.get("expected_file_id")),
            params=cls._parse_params(operation, payload.get("params")),
            protocol_version=PROTOCOL_VERSION,
        )

    @staticmethod
    def _parse_file_id(raw: Any) -> tuple[int, int, int] | None:
        if raw is None:
            return None
        if not isinstance(raw, (list, tuple)) or len(raw) != 3:
            raise ProtocolError(
                "Field 'expected_file_id' must be null or a three-element array"
            )
        if not all(isinstance(part, int) and not isinstance(part, bool) for part in raw):
            raise ProtocolError("Field 'expected_file_id' must contain three integers")
        return (int(raw[0]), int(raw[1]), int(raw[2]))

    @staticmethod
    def _parse_issued_at(raw: Any) -> _dt.datetime:
        if not isinstance(raw, str):
            raise ProtocolError("Field 'issued_at' must be an ISO-8601 string")
        try:
            parsed = _dt.datetime.fromisoformat(raw)
        except ValueError:
            raise ProtocolError(
                f"Field 'issued_at' is not a valid ISO-8601 timestamp: {raw!r}"
            ) from None
        if parsed.tzinfo is None:
            raise ProtocolError(
                "Field 'issued_at' must carry a timezone offset; a naive timestamp "
                "cannot be compared across processes"
            )
        return parsed

    @staticmethod
    def _parse_params(operation: PrivilegedOperation, raw: Any) -> dict[str, str]:
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ProtocolError("Field 'params' must be an object")

        allowed = ALLOWED_PARAMS.get(operation, frozenset())
        parsed: dict[str, str] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                raise ProtocolError("Parameter names must be strings")
            for pattern in FORBIDDEN_PARAM_PATTERNS:
                if pattern.search(key):
                    raise ProtocolError(
                        f"Parameter {key!r} names secret material. The privileged "
                        "service reads its own secrets from its own environment "
                        "and accepts none over the boundary."
                    )
            if key not in allowed:
                raise ProtocolError(
                    f"Operation {operation.value!r} accepts no parameter {key!r}. "
                    f"Accepted: {sorted(allowed) if allowed else 'none'}"
                )
            if not isinstance(value, str):
                raise ProtocolError(f"Parameter {key!r} must be a string")
            reject_command_markers(f"params.{key}", value)
            parsed[key] = value

        missing = allowed - set(parsed)
        if missing:
            raise ProtocolError(
                f"Operation {operation.value!r} requires parameter(s) {sorted(missing)}"
            )
        return parsed


@dataclass(frozen=True)
class PrivilegedResponse:
    """A structured result. Never shell output, never a raw exception.

    ``docs/PRIVILEGE_BOUNDARY.md`` requires structured status rather than command
    output, so handlers return data and the service converts anything unexpected
    into a ``FAILED`` response carrying a message it chose - never a traceback,
    which would leak privileged-side paths and internals to the unprivileged
    caller.
    """

    request_id: str
    operation: PrivilegedOperation
    operation_id: str
    status: ResponseStatus
    result: dict[str, Any] = field(default_factory=dict)
    refusals: tuple[str, ...] = ()
    message: str = ""

    @property
    def refused(self) -> bool:
        return self.status is ResponseStatus.REFUSED

    @property
    def completed(self) -> bool:
        return self.status is ResponseStatus.COMPLETED

    def to_wire(self) -> dict[str, Any]:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": self.request_id,
            "operation": self.operation.value,
            "operation_id": self.operation_id,
            "status": self.status.value,
            "result": self.result,
            "refusals": list(self.refusals),
            "message": self.message,
        }

    @classmethod
    def from_wire(cls, payload: Any) -> PrivilegedResponse:
        if not isinstance(payload, dict):
            raise ProtocolError("Privileged response must be a JSON object")
        try:
            operation = PrivilegedOperation(payload["operation"])
            status = ResponseStatus(payload["status"])
        except (KeyError, ValueError) as exc:
            raise ProtocolError(f"Malformed privileged response: {exc}") from None

        result = payload.get("result") or {}
        if not isinstance(result, dict):
            raise ProtocolError("Field 'result' must be an object")
        refusals = payload.get("refusals") or []
        if not isinstance(refusals, list):
            raise ProtocolError("Field 'refusals' must be an array")

        return cls(
            request_id=str(payload.get("request_id", "")),
            operation=operation,
            operation_id=str(payload.get("operation_id", "")),
            status=status,
            result=result,
            refusals=tuple(str(r) for r in refusals),
            message=str(payload.get("message", "")),
        )
