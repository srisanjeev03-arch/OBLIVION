"""The privileged service: the only component that touches destructive APIs.

What this component is for
--------------------------
The FastAPI process runs unprivileged. Operations that need more authority are
described to this service as structured requests, and this service decides -
independently - whether to perform them. It is deliberately small: dispatch,
authentication, validation, and a thin call into the existing engines. No
application logic lives here, because every line here runs with more authority
than the rest of the system.

What authentication across this boundary does and does not prove
---------------------------------------------------------------
Requests carry an HMAC computed over the canonical request bytes with a shared
secret held by both processes. That proves **the request came from a process
holding the service key and was not altered in transit**. It does not prove
which human is behind it: a privileged service cannot authenticate an end user,
and pretending otherwise would be the most dangerous kind of false assurance.

Responses are authenticated too, with a key derived from the same secret, over
the response bytes *and* the digest of the request they answer. Whoever holds
the pipe endpoint therefore cannot tell the API that an operation completed,
failed or was refused unless it holds the service key - and a genuine answer to
one request cannot be presented as the answer to another (finding PS-1).

The human is authenticated by the API, whose session-derived actor identity is
carried in ``actor_id`` and recorded for audit. If the API process is
compromised, the attacker inherits its authority - which is precisely why this
service still enforces containment, policy, target identity and the operation
allowlist itself, so that inherited authority is bounded rather than total.

There is no fallback key. A service with no configured key is UNAVAILABLE and
refuses everything, because the alternative - a default secret - is
indistinguishable from no authentication at all.
"""

from __future__ import annotations

import datetime as _dt
import hmac
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Final

from oblivion.core.discovery import StorageProfiler
from oblivion.core.discovery.analyzer import TargetAnalyzer
from oblivion.core.erasure.engine import ErasureEngine, ErasureMode
from oblivion.core.erasure.events import EngineEventEmitter
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.evidence.canonicalize import CanonicalizationError, canonicalize
from oblivion.core.safety.paths import SafePathValidator
from oblivion.privileged.protocol import (
    PrivilegedOperation,
    PrivilegedRequest,
    PrivilegedResponse,
    ProtocolError,
    ResponseStatus,
)
from oblivion.privileged.validation import (
    DEFAULT_MAX_REQUEST_AGE,
    PrivilegedRequestValidator,
    ValidationOutcome,
)

logger = logging.getLogger(__name__)

ENV_IPC_KEY: Final = "OBLIVION_IPC_KEY"
ENV_VAULT_KEY: Final = "OBLIVION_VAULT_KEY"
ENV_VAULT_ROOT: Final = "OBLIVION_VAULT_ROOT"
#: The name the API historically read. Honoured as a fallback so the API and the
#: privileged service always resolve one vault, never two.
ENV_VAULT_DIR: Final = "OBLIVION_VAULT_DIR"

#: Default wall-clock budget for a single privileged operation.
DEFAULT_OPERATION_TIMEOUT_SECONDS: Final = 300.0

#: Label for deriving the response-MAC key from the IPC secret. Requests are
#: MACed with the secret itself over canonical JSON (which always begins with
#: ``{``), so no request MAC can ever equal this derivation, and a key the API
#: uses to *sign* can never be used to forge what the service *answers*.
RESPONSE_KEY_LABEL: Final = b"OBLIVION-PRIV-1/derive/response-mac-key/v1"

#: Domain tag inside every response-MAC input.
RESPONSE_MAC_DOMAIN: Final = "OBLIVION-PRIV-1/response-mac/v1"

#: Wire field carrying the response MAC. Excluded from the MAC input.
RESPONSE_MAC_FIELD: Final = "mac"


class ServiceState(str, Enum):
    """Whether the service can accept work, and why not when it cannot.

    Reported rather than inferred. A caller that cannot reach the service and a
    service that is running but refuses to act are different situations, and the
    pipeline above needs to tell them apart to decide whether an operation is
    retryable.
    """

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE_NO_KEY = "UNAVAILABLE_NO_KEY"
    UNAVAILABLE_NO_ROOTS = "UNAVAILABLE_NO_ROOTS"


class CapabilityState(str, Enum):
    """Whether a capability genuinely works in this environment.

    ``SUPPORTED`` means implemented and exercised here. ``UNAVAILABLE`` means the
    environment cannot provide it - not that it silently degrades to something
    weaker. Nothing in this system may report success for an unavailable
    capability.
    """

    SUPPORTED = "SUPPORTED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class Capability:
    """One thing the privileged service can or cannot do here, and why."""

    name: str
    state: CapabilityState
    detail: str


class PrivilegedServiceError(Exception):
    """Raised for service-level faults that are not a caller's fault."""


class AuthenticationError(Exception):
    """Raised when a request's integrity or authenticity cannot be established."""


class ResponseAuthenticationError(AuthenticationError):
    """Raised when a response is not an authentic answer to the request sent."""


class ReplayCacheFull(Exception):
    """Raised when the cache cannot admit a nonce without forgetting a live one.

    Forgetting a live nonce would silently re-open the replay window for it, so
    the cache refuses instead. Fail-closed: a refused legitimate request is
    recoverable, an accepted replay is not.
    """


class ReplayCache:
    """Remembers recently seen nonces so a captured request cannot be replayed.

    **Lifetime is the security property.** This object must outlive individual
    requests. A cache constructed per request remembers nothing and refuses
    nothing - which is precisely the defect audit finding M-1 recorded. The API
    therefore holds one on ``app.state`` for the life of the application; see
    ``get_privileged_client``.

    Retention is scoped to the same window the validator uses for freshness: a
    nonce older than that window need not be remembered, because a request
    carrying it is refused as stale anyway. Keeping the two numbers equal is what
    bounds the memory without opening a gap between them.

    Thread-safe. ``remember`` is a single atomic check-and-insert under a lock,
    because the two halves are only a security control together: between a bare
    check and a bare insert, a second thread bearing the same nonce would also
    see "not seen".
    """

    #: Hard ceiling on retained nonces. With the default five-minute window this
    #: is roughly 300 requests per second sustained before the bound is reached,
    #: far above anything this workload produces - so in practice the expiry
    #: sweep, not this, is what bounds the cache. It exists so that memory is
    #: bounded by construction rather than by an assumption about traffic.
    DEFAULT_MAX_ENTRIES: Final = 100_000

    def __init__(
        self,
        window: _dt.timedelta = DEFAULT_MAX_REQUEST_AGE,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._window = window
        self._max_entries = max_entries
        self._seen: dict[str, _dt.datetime] = {}
        self._lock = threading.Lock()

    def remember(self, nonce: str, *, now: _dt.datetime | None = None) -> bool:
        """Record a nonce atomically. Returns False if it has already been used.

        The eviction sweep, the membership check and the insert all happen under
        one lock, so two concurrent requests bearing one nonce cannot both be
        accepted: exactly one sees it as new.

        Raises :class:`ReplayCacheFull` when the cache is at capacity after
        evicting everything expired.
        """
        current = now or _dt.datetime.now(_dt.timezone.utc)
        with self._lock:
            self._evict(current)
            if nonce in self._seen:
                return False
            if len(self._seen) >= self._max_entries:
                raise ReplayCacheFull(
                    f"The replay cache holds {len(self._seen)} unexpired nonces, "
                    f"its limit of {self._max_entries}. Admitting another would "
                    "mean forgetting one that is still live, which would re-open "
                    "its replay window."
                )
            self._seen[nonce] = current + self._window
            return True

    def _evict(self, now: _dt.datetime) -> None:
        """Drop expired nonces. Caller must hold the lock."""
        expired = [nonce for nonce, until in self._seen.items() if until <= now]
        for nonce in expired:
            del self._seen[nonce]

    def __len__(self) -> int:
        with self._lock:
            return len(self._seen)


class RequestAuthenticator:
    """Authenticates both directions of the privileged exchange.

    Requests: HMAC-SHA256 under the IPC secret over
    :meth:`PrivilegedRequest.to_bytes`, the canonical encoding - so integrity is
    defined over exactly the bytes the service will act on.

    Responses: HMAC-SHA256 under ``HMAC-SHA256(secret, RESPONSE_KEY_LABEL)``
    over the canonical encoding of::

        {"domain": RESPONSE_MAC_DOMAIN,
         "request_digest": <SHA-256 of the request's canonical bytes>,
         "response": <response wire, including nonce and request_digest>}

    The verifier supplies ``request_digest`` from the request *it* sent, so a
    response is only accepted as the answer to that exact request.
    """

    def __init__(self, key: bytes) -> None:
        if not key:
            raise PrivilegedServiceError(
                "Refusing to construct an authenticator with an empty key"
            )
        self._key = key
        self._response_key = hmac.new(key, RESPONSE_KEY_LABEL, sha256).digest()

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> RequestAuthenticator | None:
        """Load the shared key, or return None when none is configured.

        Returning None rather than inventing a key is the whole point: a
        deployment that forgot to configure IPC authentication must fail closed
        and visibly, not run with a well-known default.
        """
        source = env if env is not None else dict(os.environ)
        raw = source.get(ENV_IPC_KEY, "").strip()
        if not raw:
            return None
        try:
            key = bytes.fromhex(raw)
        except ValueError:
            raise PrivilegedServiceError(
                f"{ENV_IPC_KEY} must be hex-encoded; refusing to start with an "
                "unreadable key rather than falling back to an unauthenticated mode"
            ) from None
        if len(key) < 32:
            raise PrivilegedServiceError(
                f"{ENV_IPC_KEY} must be at least 32 bytes (64 hex characters)"
            )
        return cls(key)

    def sign(self, request: PrivilegedRequest) -> str:
        return hmac.new(self._key, request.to_bytes(), sha256).hexdigest()

    def verify(self, request: PrivilegedRequest, mac: str) -> None:
        """Constant-time verification. Raises rather than returning a boolean.

        A boolean return invites ``if not verify(...)`` to be written without the
        ``not``; raising makes the failure path impossible to fall through.
        """
        expected = self.sign(request)
        if not hmac.compare_digest(expected, mac or ""):
            raise AuthenticationError(
                "Request MAC does not verify. The request was not produced by a "
                "holder of the service key, or it was altered in transit."
            )

    # -- responses -------------------------------------------------------

    def _response_mac(self, request_digest: str, body: dict[str, Any]) -> str:
        message = canonicalize(
            {
                "domain": RESPONSE_MAC_DOMAIN,
                "request_digest": request_digest,
                "response": body,
            }
        )
        return hmac.new(self._response_key, message, sha256).hexdigest()

    def seal_response(
        self, request: PrivilegedRequest, response: PrivilegedResponse
    ) -> dict[str, Any]:
        """Render ``response`` to the wire, bound to ``request`` and MACed.

        Raises :class:`CanonicalizationError` when the result has no canonical
        form; the caller decides what to send instead.
        """
        body = response.to_wire()
        body["nonce"] = request.nonce
        body["request_digest"] = request.digest()
        sealed = dict(body)
        sealed[RESPONSE_MAC_FIELD] = self._response_mac(body["request_digest"], body)
        return sealed

    def verify_response(
        self, request: PrivilegedRequest, payload: Any
    ) -> PrivilegedResponse:
        """Accept ``payload`` only as an authentic answer to ``request``.

        Raises :class:`ResponseAuthenticationError` on any doubt. Nothing from
        the payload is returned unless every check below has passed.
        """
        if not isinstance(payload, dict):
            raise ResponseAuthenticationError("Privileged response is not a JSON object")

        mac = payload.get(RESPONSE_MAC_FIELD)
        if not isinstance(mac, str) or not mac:
            raise ResponseAuthenticationError(
                "Privileged response carries no MAC; an unauthenticated response is "
                "never accepted, whatever it claims"
            )
        body = {k: v for k, v in payload.items() if k != RESPONSE_MAC_FIELD}
        expected_digest = request.digest()

        if body.get("nonce") != request.nonce:
            raise ResponseAuthenticationError(
                "Privileged response nonce does not match the request nonce"
            )
        if body.get("request_digest") != expected_digest:
            raise ResponseAuthenticationError(
                "Privileged response is not bound to this request (request digest "
                "mismatch)"
            )
        if body.get("request_id") != request.request_id or body.get(
            "operation_id"
        ) != request.operation_id:
            raise ResponseAuthenticationError(
                "Privileged response request identity does not match the request"
            )

        try:
            response = PrivilegedResponse.from_wire(body)
            reconstructed = response.to_wire()
            reconstructed["nonce"] = body["nonce"]
            reconstructed["request_digest"] = body["request_digest"]
            canonical_ok = canonicalize(reconstructed) == canonicalize(body)
        except (ProtocolError, CanonicalizationError) as exc:
            raise ResponseAuthenticationError(
                f"Privileged response is malformed: {exc}"
            ) from None
        if not canonical_ok:
            raise ResponseAuthenticationError(
                "Privileged response cannot be canonically reconstructed; it carries "
                "fields or values outside the response contract"
            )
        if response.operation is not request.operation:
            raise ResponseAuthenticationError(
                "Privileged response operation does not match the request"
            )

        expected_mac = self._response_mac(expected_digest, body)
        if not hmac.compare_digest(
            expected_mac.encode("ascii"), mac.encode("utf-8", "surrogatepass")
        ):
            raise ResponseAuthenticationError(
                "Privileged response MAC does not verify. It was not produced by a "
                "holder of the service key, or it was altered in transit."
            )
        return response


@dataclass
class CancellationToken:
    """Cooperative cancellation for the operations where stopping is safe.

    Only checked between whole items - never mid-write. A partially completed
    destructive operation that stopped halfway would leave the filesystem and
    the persisted operation state disagreeing, which is worse than finishing.
    """

    _cancelled: bool = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


@dataclass
class ServiceConfig:
    """Everything the service needs, supplied explicitly.

    Constructed by the process that starts the service. Nothing here is read
    from a request.
    """

    validator: SafePathValidator
    authenticator: RequestAuthenticator | None
    vault_root: str | None = None
    vault_key: bytes | None = None
    operation_timeout_seconds: float = DEFAULT_OPERATION_TIMEOUT_SECONDS
    max_request_age: _dt.timedelta = DEFAULT_MAX_REQUEST_AGE

    #: The nonce cache to use. Supplying one lets a host keep replay protection
    #: alive across many short-lived service objects, which is what the HTTP
    #: deployment needs: the service is cheap to rebuild per request, but a
    #: cache rebuilt per request remembers nothing. Left unset, the service owns
    #: a private cache and replay protection lasts exactly as long as it does.
    replay_cache: ReplayCache | None = None


class PrivilegedService:
    """Dispatches allowlisted operations after deciding for itself.

    Dispatch is an explicit mapping from enum member to bound method. It is
    never a name lookup on the instance: attribute-based dispatch would let a
    request's contents select which code runs, which is the class of bug this
    entire boundary exists to prevent.
    """

    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._validator = PrivilegedRequestValidator(
            config.validator, max_request_age=config.max_request_age
        )
        # `is not None`, never `or`: ReplayCache defines __len__, so an empty
        # cache is falsy, and `config.replay_cache or ReplayCache(...)` would
        # silently discard an injected-but-empty cache and build a private one -
        # reintroducing M-1 in the exact case that matters, the first request
        # after startup.
        self._replay = (
            config.replay_cache
            if config.replay_cache is not None
            else ReplayCache(config.max_request_age)
        )
        self._analyzer = TargetAnalyzer(config.validator)
        self._profiler = StorageProfiler()
        self._emitter = EngineEventEmitter()
        self._handlers: dict[
            PrivilegedOperation,
            Callable[[PrivilegedRequest, ValidationOutcome], dict[str, Any]],
        ] = {
            PrivilegedOperation.INSPECT_TARGET: self._inspect_target,
            PrivilegedOperation.SCAN_SCOPE: self._scan_scope,
            PrivilegedOperation.DELETE_FILE: self._delete_file,
            PrivilegedOperation.DELETE_TREE: self._delete_tree,
            PrivilegedOperation.PREPARE_RECOVERY_OBJECT: self._prepare_recovery_object,
            PrivilegedOperation.RESTORE_RECOVERY_OBJECT: self._restore_recovery_object,
        }

    # -- state and capability reporting ---------------------------------

    @property
    def state(self) -> ServiceState:
        if self._config.authenticator is None:
            return ServiceState.UNAVAILABLE_NO_KEY
        if not self._config.validator.allowed_roots:
            return ServiceState.UNAVAILABLE_NO_ROOTS
        return ServiceState.AVAILABLE

    @property
    def available(self) -> bool:
        return self.state is ServiceState.AVAILABLE

    def capabilities(self) -> tuple[Capability, ...]:
        """Report what actually works here, honestly.

        ``media_sanitization`` is reported UNAVAILABLE on purpose. This build
        performs no overwrite of any kind, and a capability report that implied
        sanitization would be the single most misleading thing this system could
        say. See ``docs/OBLIVION_DOCUMENTATION.md §15``.
        """
        vault_ready = bool(self._config.vault_root and self._config.vault_key)
        return (
            Capability(
                "logical_file_deletion",
                CapabilityState.SUPPORTED,
                "Unlinks a validated file after target-identity revalidation.",
            ),
            Capability(
                "logical_tree_deletion",
                CapabilityState.SUPPORTED,
                "Removes a validated directory tree. Logical removal only.",
            ),
            Capability(
                "media_sanitization",
                CapabilityState.UNAVAILABLE,
                "No overwrite, block-level or device sanitization is performed. "
                "This build cannot and does not claim physical irrecoverability.",
            ),
            Capability(
                "recovery_vault",
                CapabilityState.SUPPORTED
                if vault_ready
                else CapabilityState.UNAVAILABLE,
                "AES-256-GCM recovery objects with verified round-trip."
                if vault_ready
                else "No vault root or vault key is configured in this process.",
            ),
            Capability(
                "raw_volume_access",
                CapabilityState.UNAVAILABLE,
                "This service does not open raw physical-drive handles. Recovery "
                "testing is therefore filesystem-level, not media-level.",
            ),
        )

    # -- request handling -----------------------------------------------

    def handle(
        self,
        request: PrivilegedRequest,
        mac: str,
        *,
        now: _dt.datetime | None = None,
    ) -> PrivilegedResponse:
        """Authenticate, validate, then dispatch. Never raises to the caller.

        Any unexpected exception becomes a ``FAILED`` response with a message
        this service chose. A traceback crossing the boundary would leak
        privileged-side paths and internals to a less-trusted process.
        """
        if not self.available:
            return self._refuse(
                request,
                (
                    f"Privileged service is {self.state.value}. It refuses all work "
                    "until correctly configured; it does not degrade to an "
                    "unauthenticated mode.",
                ),
            )

        authenticator = self._config.authenticator
        if authenticator is None:  # pragma: no cover - guarded by self.available
            return self._refuse(request, ("No authenticator configured",))

        try:
            authenticator.verify(request, mac)
        except AuthenticationError as exc:
            logger.warning(
                "privileged.request.rejected reason=authentication operation=%s",
                request.operation.value,
            )
            return self._refuse(request, (str(exc),))

        try:
            fresh_nonce = self._replay.remember(request.nonce, now=now)
        except ReplayCacheFull as exc:
            # Refusing work is the safe direction. The alternative - evicting a
            # live nonce to make room - would silently re-open its replay window.
            logger.error("privileged.replay_cache.full operation=%s", request.operation.value)
            return self._refuse(request, (str(exc),))

        if not fresh_nonce:
            logger.warning(
                "privileged.request.rejected reason=replay operation=%s",
                request.operation.value,
            )
            return self._refuse(
                request,
                (
                    "Nonce has already been used. A correctly formed, correctly "
                    "signed request is still refused when replayed.",
                ),
            )

        outcome = self._validator.validate(request, now=now)
        if not outcome.permitted:
            logger.info(
                "privileged.request.refused operation=%s reasons=%d",
                request.operation.value,
                len(outcome.refusals),
            )
            return self._refuse(request, outcome.refusals)

        handler = self._handlers.get(request.operation)
        if handler is None:
            # Unreachable while the handler map covers the enum; the test suite
            # pins that. Refusing here keeps the failure safe if it ever drifts.
            return self._refuse(
                request,
                (f"No handler registered for {request.operation.value!r}",),
            )

        started = time.monotonic()
        try:
            result = handler(request, outcome)
        except Exception as exc:  # noqa: BLE001 - boundary: nothing may escape
            logger.exception(
                "privileged.handler.failed operation=%s", request.operation.value
            )
            return PrivilegedResponse(
                request_id=request.request_id,
                operation=request.operation,
                operation_id=request.operation_id,
                status=ResponseStatus.FAILED,
                message=f"{type(exc).__name__} while performing the operation",
                result={"reconciliation_required": True},
            )

        elapsed = time.monotonic() - started
        result["duration_seconds"] = round(elapsed, 6)

        if elapsed > self._config.operation_timeout_seconds:
            # The work is already done - a filesystem call cannot be recalled
            # once it has returned. Reporting COMPLETED would hide that the
            # caller stopped waiting, so this is surfaced as a state the
            # pipeline must reconcile against the actual filesystem.
            result["reconciliation_required"] = True
            return PrivilegedResponse(
                request_id=request.request_id,
                operation=request.operation,
                operation_id=request.operation_id,
                status=ResponseStatus.FAILED,
                result=result,
                message=(
                    f"Operation exceeded the "
                    f"{self._config.operation_timeout_seconds:.0f}s budget. It may "
                    "have completed; the persisted operation state must be "
                    "reconciled against the filesystem."
                ),
            )

        return PrivilegedResponse(
            request_id=request.request_id,
            operation=request.operation,
            operation_id=request.operation_id,
            status=ResponseStatus.COMPLETED,
            result=result,
        )

    def respond(
        self,
        request: PrivilegedRequest,
        mac: str,
        *,
        now: _dt.datetime | None = None,
    ) -> dict[str, Any]:
        """Handle ``request`` and return the wire reply, sealed when possible.

        A reply is sealed only for a request whose MAC verified. A service with
        no key, or a request not produced by a key holder, gets an unsealed
        refusal: the client rejects it, which is the fail-closed outcome, and
        the service never MACs an answer to input it could not authenticate.
        """
        response = self.handle(request, mac, now=now)
        authenticator = self._config.authenticator
        if authenticator is None:
            return response.to_wire()
        try:
            authenticator.verify(request, mac)
        except AuthenticationError:
            return response.to_wire()

        try:
            return authenticator.seal_response(request, response)
        except CanonicalizationError:
            # The work may already be done, so this is FAILED-and-reconcile, not
            # a refusal - and never an unauthenticated copy of the real result.
            logger.error(
                "privileged.response.unencodable operation=%s", request.operation.value
            )
            return authenticator.seal_response(
                request,
                PrivilegedResponse(
                    request_id=request.request_id,
                    operation=request.operation,
                    operation_id=request.operation_id,
                    status=ResponseStatus.FAILED,
                    result={"reconciliation_required": True},
                    message=(
                        "The operation result has no canonical encoding, so it "
                        "could not be authenticated. It may have completed; the "
                        "persisted operation state must be reconciled."
                    ),
                ),
            )

    def _refuse(
        self, request: PrivilegedRequest, refusals: tuple[str, ...]
    ) -> PrivilegedResponse:
        return PrivilegedResponse(
            request_id=request.request_id,
            operation=request.operation,
            operation_id=request.operation_id,
            status=ResponseStatus.REFUSED,
            refusals=tuple(refusals),
            message="The privileged service refused this request.",
        )

    # -- handlers --------------------------------------------------------

    def _engine(self) -> ErasureEngine:
        """A fresh engine per operation.

        The engine carries a state machine, so reusing one instance across
        operations would let one operation's state leak into the next.
        """
        engine = ErasureEngine(self._config.validator, self._emitter)
        if self._config.vault_root and self._config.vault_key:
            vault = RecoveryVault(
                self._config.vault_root,
                self._config.validator,
                self._config.vault_key,
            )
            engine.set_vault(vault, self._config.vault_key)
        return engine

    # The read-only handlers take `request` they do not read, because every
    # handler shares one signature so the dispatch table can be a plain mapping.
    # Varying the signatures would push a branch into dispatch, which is the one
    # place in this package that must stay trivially auditable.

    def _inspect_target(
        self,
        request: PrivilegedRequest,  # noqa: ARG002 - uniform dispatch signature
        outcome: ValidationOutcome,
    ) -> dict[str, Any]:
        return {"analysis": self._analyzer.analyze(str(outcome.canonical_path))}

    def _scan_scope(
        self,
        request: PrivilegedRequest,  # noqa: ARG002 - uniform dispatch signature
        outcome: ValidationOutcome,
    ) -> dict[str, Any]:
        return {"storage_profile": self._profiler.profile(str(outcome.canonical_path))}

    def _delete_file(
        self, request: PrivilegedRequest, outcome: ValidationOutcome
    ) -> dict[str, Any]:
        return self._engine().execute_operation(
            ErasureMode.SELECTIVE_PERMANENT,
            request.operation_id,
            str(outcome.canonical_path),
            str(outcome.volume_serial),
            target_file_id=outcome.file_id,
        )

    def _delete_tree(
        self, request: PrivilegedRequest, outcome: ValidationOutcome
    ) -> dict[str, Any]:
        return self._engine().execute_operation(
            ErasureMode.COMPLETE_ERASURE,
            request.operation_id,
            str(outcome.canonical_path),
            str(outcome.volume_serial),
            target_file_id=outcome.file_id,
        )

    def _prepare_recovery_object(
        self, request: PrivilegedRequest, outcome: ValidationOutcome
    ) -> dict[str, Any]:
        if not (self._config.vault_root and self._config.vault_key):
            # Reported as a capability fact rather than raised: the caller needs
            # to distinguish "this deployment has no vault" from "the vault
            # failed", and only the latter is a fault.
            return {
                "status": "BLOCKED",
                "error": "VAULT_UNAVAILABLE",
                "capability": CapabilityState.UNAVAILABLE.value,
                "detail": "No vault root or vault key is configured for this service.",
            }
        return self._engine().execute_operation(
            ErasureMode.CONTROLLED_RECOVERABLE,
            request.operation_id,
            str(outcome.canonical_path),
            str(outcome.volume_serial),
            target_file_id=outcome.file_id,
        )

    def _restore_recovery_object(
        self, request: PrivilegedRequest, outcome: ValidationOutcome
    ) -> dict[str, Any]:
        if not (self._config.vault_root and self._config.vault_key):
            return {
                "status": "BLOCKED",
                "error": "VAULT_UNAVAILABLE",
                "capability": CapabilityState.UNAVAILABLE.value,
                "detail": "No vault root or vault key is configured for this service.",
            }
        object_id = request.params["object_id"]
        vault = RecoveryVault(
            self._config.vault_root, self._config.validator, self._config.vault_key
        )
        if not vault.exists(object_id):
            # Reported before any decryption or write, so "no such object" is an
            # answer rather than a decryption failure.
            return {"status": "BLOCKED", "error": "RECOVERY_OBJECT_NOT_FOUND"}
        # The key comes from this process's own configuration. The request names
        # the object and the destination and nothing else; it cannot supply,
        # substitute or influence the key.
        return self._engine().restore_recovery_object(
            object_id,
            str(outcome.destination_path),
            self._config.vault_key,
            authorized=True,
            allow_overwrite=False,
        )


def resolve_vault_root(env: dict[str, str] | None = None) -> str | None:
    """The configured vault root, shared by the API and the privileged service."""
    source = env if env is not None else dict(os.environ)
    return (source.get(ENV_VAULT_ROOT) or source.get(ENV_VAULT_DIR) or "").strip() or None


def build_service_from_env(
    validator: SafePathValidator,
    env: dict[str, str] | None = None,
    *,
    replay_cache: ReplayCache | None = None,
) -> PrivilegedService:
    """Construct a service from process configuration.

    Every secret is read here, from this process's environment. A service built
    this way with nothing configured is UNAVAILABLE and refuses work - which is
    the correct behaviour, and is asserted by the test suite.

    ``replay_cache`` lets a host that rebuilds the service frequently - the HTTP
    API does, once per request - keep one cache alive across all of them. Omit
    it and the service owns a private cache, which is correct only when the
    service itself is long-lived.
    """
    source = env if env is not None else dict(os.environ)

    vault_key: bytes | None = None
    raw_vault_key = source.get(ENV_VAULT_KEY, "").strip()
    if raw_vault_key:
        try:
            candidate = bytes.fromhex(raw_vault_key)
        except ValueError:
            candidate = b""
        # A wrong-length key is treated as absent rather than padded or hashed
        # into shape; silently deriving a key from malformed input would make a
        # misconfiguration look like a working vault.
        vault_key = candidate if len(candidate) == 32 else None

    return PrivilegedService(
        ServiceConfig(
            validator=validator,
            authenticator=RequestAuthenticator.from_env(source),
            vault_root=resolve_vault_root(source),
            vault_key=vault_key,
            replay_cache=replay_cache,
        )
    )
