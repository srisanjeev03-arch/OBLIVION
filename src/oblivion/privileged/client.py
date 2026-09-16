"""The unprivileged side's handle on the privileged service.

This is the only supported way for application code to reach privileged
operations. It exists so that callers cannot accidentally construct a partial
request: every call here mints a fresh nonce, stamps a timezone-aware issue
time, and signs the canonical bytes, so a request is complete and authenticated
or it does not exist.

On actor identity
-----------------
``actor_id`` is carried across the boundary for **attribution**, not for
authorization. The API derives it from the authenticated session before calling
here; it must never be taken from a request body or query parameter. The
privileged service, in turn, does not use it to grant anything - it enforces
containment, policy and target identity itself. Both halves of that arrangement
are necessary: the identity makes privileged acts auditable, and the service's
independent checks make a forged identity useless for widening authority.
"""

from __future__ import annotations

import datetime as _dt
import secrets
from typing import Any

from oblivion.privileged.protocol import (
    PrivilegedOperation,
    PrivilegedRequest,
    PrivilegedResponse,
)
from oblivion.privileged.service import RequestAuthenticator, ResponseAuthenticationError
from oblivion.privileged.transport import (
    ServiceUnavailableError,
    Transport,
    TransportError,
)

__all__ = [
    "PrivilegedClient",
    "PrivilegedClientError",
    "ServiceUnavailableError",
    "new_nonce",
]


class PrivilegedClientError(Exception):
    """Raised when a request could not be formed or its reply not understood."""


def new_nonce() -> str:
    """A single-use value for replay protection.

    128 bits from the system CSPRNG. A collision would cause a legitimate
    request to be refused as a replay, so the width is chosen to make that not
    happen rather than merely to be unpredictable.
    """
    return secrets.token_hex(16)


class PrivilegedClient:
    """Builds, signs and sends privileged requests."""

    def __init__(
        self,
        transport: Transport,
        authenticator: RequestAuthenticator,
    ) -> None:
        self._transport = transport
        self._authenticator = authenticator

    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def isolated(self) -> bool:
        """Whether requests actually leave this process.

        Exposed so a caller that requires genuine privilege separation can
        assert it rather than trusting the deployment to have been wired
        correctly.
        """
        return self._transport.isolated

    def send(self, request: PrivilegedRequest) -> PrivilegedResponse:
        """Sign, exchange, and return only an authenticated, bound response."""
        envelope = {
            "request": request.to_wire(),
            "mac": self._authenticator.sign(request),
        }
        try:
            payload = self._transport.exchange(envelope)
        except ServiceUnavailableError:
            # Propagated unchanged. "Unreachable" must not be flattened into a
            # refusal, because the caller learned nothing about the request and
            # the operation may be retryable.
            raise
        except TransportError as exc:
            raise PrivilegedClientError(str(exc)) from None

        # Nothing from the pipe is believed until it is proven to be the service's
        # answer to *this* request. Whoever holds the endpoint otherwise decides
        # what the pipeline records as having happened (finding PS-1).
        try:
            return self._authenticator.verify_response(request, payload)
        except ResponseAuthenticationError as exc:
            raise PrivilegedClientError(
                f"Privileged service response rejected: {exc}"
            ) from None

    def request(
        self,
        operation: PrivilegedOperation,
        *,
        operation_id: str,
        policy_id: str,
        mode: str,
        target_path: str,
        target_type: str,
        actor_id: str,
        expected_volume_serial: str | None = None,
        expected_file_id: tuple[int, int, int] | None = None,
        params: dict[str, str] | None = None,
    ) -> PrivilegedResponse:
        """Build a complete request and send it.

        Every field the boundary needs is a required keyword. There is no
        overload that omits target identity or policy: a caller that does not
        have them is not ready to ask for privileged work.
        """
        request = PrivilegedRequest(
            request_id=f"req-{new_nonce()}",
            nonce=new_nonce(),
            operation=operation,
            operation_id=operation_id,
            policy_id=policy_id,
            mode=mode,
            target_path=target_path,
            target_type=target_type,
            actor_id=actor_id,
            issued_at=_dt.datetime.now(_dt.timezone.utc),
            expected_volume_serial=expected_volume_serial,
            expected_file_id=expected_file_id,
            params=dict(params or {}),
        )
        return self.send(request)

    # -- convenience wrappers -------------------------------------------
    #
    # Thin by design: they name the operation and forward. Logic added here
    # would be logic the privileged service does not know about, and therefore
    # logic that is not enforced.

    def inspect_target(self, **kwargs: Any) -> PrivilegedResponse:
        return self.request(PrivilegedOperation.INSPECT_TARGET, **kwargs)

    def scan_scope(self, **kwargs: Any) -> PrivilegedResponse:
        return self.request(PrivilegedOperation.SCAN_SCOPE, **kwargs)

    def delete_file(self, **kwargs: Any) -> PrivilegedResponse:
        return self.request(PrivilegedOperation.DELETE_FILE, **kwargs)

    def delete_tree(self, **kwargs: Any) -> PrivilegedResponse:
        return self.request(PrivilegedOperation.DELETE_TREE, **kwargs)

    def prepare_recovery_object(self, **kwargs: Any) -> PrivilegedResponse:
        return self.request(PrivilegedOperation.PREPARE_RECOVERY_OBJECT, **kwargs)

    def restore_recovery_object(self, **kwargs: Any) -> PrivilegedResponse:
        return self.request(PrivilegedOperation.RESTORE_RECOVERY_OBJECT, **kwargs)
