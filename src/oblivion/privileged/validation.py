"""Privileged-side validation: the decision the boundary exists to make.

The unprivileged API validates too, and it should. That validation is *advice*.
This module re-derives every safety-relevant fact from the privileged process's
own configuration and the live filesystem, because a boundary that trusts the
caller's word about containment, policy or target identity is not a boundary.

The check order follows ``docs/PRIVILEGE_BOUNDARY.md``. Two rules shape it:

* **The service's allowed roots are the service's own.** A request cannot
  contribute, extend or override them. This is the single control that keeps a
  compromised API process from turning the privileged service into a
  general-purpose file deleter.
* **Refusals accumulate, then refuse.** Every applicable reason is collected so
  the response explains the full picture, but a single reason is enough to
  refuse. Nothing here can return "permitted" with reasons attached.
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from oblivion.core.policy.engine import PolicyEngine, PolicyError
from oblivion.core.safety.paths import SafePathValidator
from oblivion.privileged.protocol import (
    DESTRUCTIVE_OPERATIONS,
    RESTORE_OPERATIONS,
    PrivilegedOperation,
    PrivilegedRequest,
)

#: How stale a request may be before the service refuses it. Bounds the window
#: in which a captured request is useful, and bounds how long the replay cache
#: must remember a nonce - the two numbers are deliberately the same one.
DEFAULT_MAX_REQUEST_AGE = _dt.timedelta(minutes=5)

#: The permission each operation requires. The privileged service checks that
#: the request *names* a permission-bearing actor and that the operation is one
#: this deployment permits; it cannot itself authenticate a human. See the
#: module note in ``service.py`` on what the channel does and does not prove.
OPERATION_PERMISSION: Final[dict[PrivilegedOperation, str]] = {
    PrivilegedOperation.INSPECT_TARGET: "operation.view",
    PrivilegedOperation.SCAN_SCOPE: "operation.view",
    PrivilegedOperation.DELETE_FILE: "file.erasure.execute",
    PrivilegedOperation.DELETE_TREE: "file.erasure.execute",
    PrivilegedOperation.PREPARE_RECOVERY_OBJECT: "file.erasure.execute",
    PrivilegedOperation.RESTORE_RECOVERY_OBJECT: "recovery.execute",
}


@dataclass(frozen=True)
class ValidationOutcome:
    """The privileged side's own answer about a request.

    ``permitted`` is true only when ``refusals`` is empty; the invariant is
    asserted in :meth:`__post_init__` rather than left to callers, so a
    half-populated outcome cannot be constructed and then acted on.
    """

    permitted: bool
    refusals: tuple[str, ...] = ()
    canonical_path: str | None = None
    volume_serial: str | None = None
    file_id: tuple[int, int, int] | None = None
    destination_path: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.permitted and self.refusals:
            raise ValueError(
                "A permitted outcome cannot carry refusals; refusing is absolute"
            )
        if not self.permitted and not self.refusals:
            raise ValueError(
                "A refusal must state why. An unexplained refusal is a bug, not a "
                "safe default."
            )


class PrivilegedRequestValidator:
    """Decides whether the privileged service will act on a request.

    Holds the service's own :class:`SafePathValidator`, whose allowed roots come
    from the privileged process's configuration. Nothing in a request can widen
    them.
    """

    def __init__(
        self,
        validator: SafePathValidator,
        *,
        max_request_age: _dt.timedelta = DEFAULT_MAX_REQUEST_AGE,
    ) -> None:
        self._validator = validator
        self._max_request_age = max_request_age

    @property
    def validator(self) -> SafePathValidator:
        return self._validator

    @property
    def max_request_age(self) -> _dt.timedelta:
        return self._max_request_age

    def validate(
        self, request: PrivilegedRequest, *, now: _dt.datetime | None = None
    ) -> ValidationOutcome:
        """Run every applicable check and return a single, explained verdict."""
        refusals: list[str] = []
        warnings: list[str] = []

        # 1. Operation type. The parser already restricted this to the
        # allowlist; re-asserting means the service is safe even if it is ever
        # handed a request built in-process rather than parsed from the wire.
        if not isinstance(request.operation, PrivilegedOperation):
            return ValidationOutcome(
                permitted=False,
                refusals=("Operation is not a member of the privileged allowlist",),
            )

        # 2. Freshness. A request older than the window is refused whether or not
        # its nonce is still remembered, so replay protection does not depend on
        # the cache alone.
        refusals.extend(self._check_freshness(request, now))

        # 3. Actor. The privileged service cannot authenticate a human; it can
        # insist that one was named, so every privileged act is attributable in
        # the audit record.
        if not request.actor_id.strip():
            refusals.append(
                "Request names no actor; privileged acts must be attributable"
            )

        # 4. Policy. Allowlisted, and compatible with this mode and target type.
        try:
            PolicyEngine.validate_operation_policy(
                request.policy_id, request.mode, request.target_type
            )
        except PolicyError as exc:
            refusals.append(f"Policy refused: {exc}")

        # 5. Operation-to-permission mapping must exist for this deployment.
        if request.operation not in OPERATION_PERMISSION:
            refusals.append(
                f"Operation {request.operation.value!r} has no permission mapping; "
                "refusing rather than defaulting to permitted"
            )

        # 6. Target: normalization, containment, reparse and system-volume
        # protection, all against the service's own roots.
        target_result = self._validator.validate_target(
            request.target_path,
            is_directory_tree=request.target_type == "directory",
            require_existing_identity=request.operation in DESTRUCTIVE_OPERATIONS,
        )
        canonical = target_result.get("canonical")
        volume_serial = target_result.get("volume_serial")
        if not target_result.get("valid"):
            refusals.extend(
                f"Target refused: {reason}"
                for reason in target_result.get("errors", ())
            )

        # 7. Target identity. For destructive work the caller must say which
        # object it means, and the service must find that same object now.
        file_id: tuple[int, int, int] | None = None
        if request.operation in DESTRUCTIVE_OPERATIONS and target_result.get("valid"):
            identity_refusals, file_id = self._check_target_identity(
                request, str(canonical), volume_serial
            )
            refusals.extend(identity_refusals)

        # 8. Restore destination. Validated as its own target, and required not
        # to exist: a restore that overwrites is a destructive operation wearing
        # a recovery operation's name.
        destination: str | None = None
        if request.operation in RESTORE_OPERATIONS:
            destination_refusals, destination = self._check_destination(request)
            refusals.extend(destination_refusals)

        if refusals:
            return ValidationOutcome(
                permitted=False,
                refusals=tuple(refusals),
                canonical_path=canonical if isinstance(canonical, str) else None,
            )

        return ValidationOutcome(
            permitted=True,
            canonical_path=str(canonical),
            volume_serial=volume_serial if isinstance(volume_serial, str) else None,
            file_id=file_id,
            destination_path=destination,
            warnings=tuple(warnings),
        )

    def _check_freshness(
        self, request: PrivilegedRequest, now: _dt.datetime | None
    ) -> list[str]:
        current = now or _dt.datetime.now(_dt.timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=_dt.timezone.utc)
        age = current - request.issued_at
        if age > self._max_request_age:
            return [
                f"Request is stale: issued {age.total_seconds():.0f}s ago, limit is "
                f"{self._max_request_age.total_seconds():.0f}s"
            ]
        # A request from the future is not merely odd; it would extend the replay
        # window arbitrarily, so it is refused with the same firmness.
        if -age > self._max_request_age:
            return [
                "Request is dated in the future beyond the permitted skew; refusing "
                "rather than extending the replay window"
            ]
        return []

    def _check_target_identity(
        self,
        request: PrivilegedRequest,
        canonical: str,
        volume_serial: str | None,
    ) -> tuple[list[str], tuple[int, int, int] | None]:
        """Confirm the caller's named object is the object now present.

        This is the pre-flight check. The erasure engine performs the same
        comparison again immediately before it acts, which is the one that
        actually closes the TOCTOU window; this one refuses early and cheaply.
        """
        refusals: list[str] = []

        if request.expected_volume_serial is None:
            refusals.append(
                "Destructive request states no expected volume serial; target "
                "identity cannot be established (fail-closed)"
            )
        elif (
            volume_serial is not None
            and request.expected_volume_serial != volume_serial
        ):
            refusals.append(
                "Expected volume serial does not match the volume now holding the "
                "target; refusing rather than acting on a substituted volume"
            )

        current_file_id = self._validator._get_file_id(canonical)
        if request.expected_file_id is not None:
            if current_file_id is None:
                refusals.append(
                    "Caller named a file identity but none can be read now; "
                    "refusing rather than assuming it still matches"
                )
            elif tuple(current_file_id) != tuple(request.expected_file_id):
                refusals.append(
                    "File identity changed between request and validation; the "
                    "object at this path is not the object the caller approved"
                )
        return refusals, current_file_id

    def _check_destination(
        self, request: PrivilegedRequest
    ) -> tuple[list[str], str | None]:
        raw_destination = request.params.get("destination_path", "")
        if not raw_destination:
            return (["Restore request names no destination"], None)

        result = self._validator.validate_target(
            raw_destination,
            is_directory_tree=False,
            require_existing_identity=False,
        )
        canonical = result.get("canonical")
        if not result.get("valid"):
            return (
                [
                    f"Destination refused: {reason}"
                    for reason in result.get("errors", ())
                ],
                None,
            )

        destination = str(canonical)
        if os.path.exists(destination):
            return (
                [
                    "Destination already exists. A restore never overwrites: the "
                    "caller must choose a path that does not yet exist."
                ],
                None,
            )
        parent = Path(destination).parent
        if not parent.is_dir():
            return ([f"Destination directory does not exist: {parent}"], None)
        return ([], destination)
