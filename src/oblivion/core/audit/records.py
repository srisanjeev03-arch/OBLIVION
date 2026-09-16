"""What one audit entry is, and what it is not allowed to contain.

An audit record states a single act: an actor, an event, an outcome, a moment,
and the operation it belonged to. It is a *statement about this system*, not a
measurement of a target - measurements are evidence, and they live in
``core/evidence/record.py``.

Three properties are enforced here rather than documented, because each one is
a control that stops working the moment it becomes optional:

1. **The actor is server-derived.** :class:`AuditActor` cannot be built from a
   request body. Its constructors name the provenance of the identity, and
   ``ActorSource`` is recorded in the hashed-over bytes, so a reader can always
   tell whether an identity was authenticated or merely asserted.
2. **Secrets cannot enter.** Metadata field names are checked against the same
   ``FORBIDDEN_FIELD_PATTERNS`` the evidence record uses. An audit log is
   retained, exported and read by people who are not the data subject; a secret
   that reaches it cannot be withdrawn.
3. **The record is immutable.** The digest is a function of the content, so a
   record that could be edited in place would carry a digest that had silently
   stopped describing it.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from oblivion.core.evidence.canonicalize import (
    CANONICALIZATION_VERSION,
    canonical_hash,
    canonicalize,
)
from oblivion.core.evidence.record import FORBIDDEN_FIELD_PATTERNS

#: Identifies the audit record shape. Recorded in every record and checked at
#: verification time, so a future shape change cannot be mistaken for this one.
AUDIT_SCHEMA_VERSION = "oblivion-audit-1"

SUPPORTED_AUDIT_SCHEMA_VERSIONS: frozenset[str] = frozenset({AUDIT_SCHEMA_VERSION})

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class AuditError(ValueError):
    """Raised when an audit record cannot be built or is malformed."""


class AuditEventType(str, Enum):
    """The acts this system records.

    A closed set. An event type that is not listed here cannot be written,
    which is what keeps the log searchable and keeps a caller from inventing a
    category to hide an act inside.
    """

    # --- authentication ---------------------------------------------------
    AUTH_LOGIN_SUCCEEDED = "AUTH_LOGIN_SUCCEEDED"
    AUTH_LOGIN_FAILED = "AUTH_LOGIN_FAILED"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    AUTH_ACCESS_DENIED = "AUTH_ACCESS_DENIED"

    # --- discovery --------------------------------------------------------
    TARGET_ANALYZED = "TARGET_ANALYZED"

    # --- the operation lifecycle, including its separation of duties ------
    OPERATION_CREATED = "OPERATION_CREATED"
    OPERATION_APPROVED = "OPERATION_APPROVED"
    OPERATION_APPROVAL_REFUSED = "OPERATION_APPROVAL_REFUSED"
    OPERATION_EXECUTED = "OPERATION_EXECUTED"
    #: Execution was asked for and declined before any destructive work began.
    #: Distinct from ``OPERATION_EXECUTED`` with a failed outcome, which asserts
    #: that execution was entered and did not complete. A declined request must
    #: never be recorded as an execution that went wrong (audit finding A-1).
    OPERATION_EXECUTION_REFUSED = "OPERATION_EXECUTION_REFUSED"
    OPERATION_CANCELLED = "OPERATION_CANCELLED"
    OPERATION_STATE_CHANGED = "OPERATION_STATE_CHANGED"
    #: The destructive step is about to be dispatched. Committed on its own,
    #: before the request is sent, so the attempt outlives any later rollback.
    #: It asserts that dispatch began - not that it arrived or what it did.
    OPERATION_DISPATCH_STARTED = "OPERATION_DISPATCH_STARTED"
    #: A dispatched destructive step whose result could not be established
    #: (response rejected, exchange broken, or result lost before it was
    #: recorded). The outcome field is FAILED because *establishing the result*
    #: failed; the destructive step itself is recorded as unknown, and the
    #: operation is left in RECONCILIATION_REQUIRED.
    OPERATION_OUTCOME_UNESTABLISHED = "OPERATION_OUTCOME_UNESTABLISHED"

    # --- the closed loop --------------------------------------------------
    PIPELINE_STARTED = "PIPELINE_STARTED"
    PIPELINE_CONCLUDED = "PIPELINE_CONCLUDED"

    # --- controlled recovery ----------------------------------------------
    RECOVERY_RESTORE_REQUESTED = "RECOVERY_RESTORE_REQUESTED"
    RECOVERY_RESTORE_PERFORMED = "RECOVERY_RESTORE_PERFORMED"

    # --- evidence and certificates ---------------------------------------
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"
    CERTIFICATE_VERIFIED = "CERTIFICATE_VERIFIED"

    # --- the log about the log --------------------------------------------
    #
    # Reading an audit log is itself a privileged act. A log that does not
    # record its own readers cannot answer "who looked at this".
    AUDIT_LOG_QUERIED = "AUDIT_LOG_QUERIED"
    AUDIT_LOG_VERIFIED = "AUDIT_LOG_VERIFIED"

    # --- the privileged boundary ------------------------------------------
    PRIVILEGED_REQUEST_REFUSED = "PRIVILEGED_REQUEST_REFUSED"


class AuditOutcome(str, Enum):
    """What became of the act.

    ``REFUSED`` and ``FAILED`` are distinct for the same reason they are
    distinct at the privileged boundary: refused means the system declined and
    nothing happened; failed means it was permitted, attempted, and did not
    complete. Those call for different responses and must not be merged.
    """

    SUCCEEDED = "SUCCEEDED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"


class ActorSource(str, Enum):
    """Where the recorded identity came from.

    This is recorded because "the system did it" and "an authenticated person
    did it" are different claims, and an audit reader must never have to guess
    which one an entry is making.
    """

    #: Resolved from a server-side session record. The only source that names a
    #: human and means it.
    AUTHENTICATED_SESSION = "AUTHENTICATED_SESSION"
    #: The application acting on its own behalf, with no human principal.
    SYSTEM = "SYSTEM"
    #: The act was performed without a valid session - a failed login, for
    #: example. No identity is asserted; any supplied name is a *claim*.
    UNAUTHENTICATED = "UNAUTHENTICATED"


@dataclass(frozen=True)
class AuditActor:
    """Who performed the act, and on what authority that is believed.

    There is deliberately no constructor that takes an identity from a request.
    The three classmethods below are the only ways to make one, and each names
    the provenance it is recording.
    """

    actor_id: str
    actor_role: str
    source: ActorSource

    def __post_init__(self) -> None:
        if not self.actor_id:
            raise AuditError("actor_id is required; an unattributed act is not auditable")

    @classmethod
    def authenticated(cls, user_id: str, role: str) -> AuditActor:
        """An identity resolved from a server-side session.

        ``user_id`` must come from the authenticated principal the session
        lookup returned - never from a body field, query parameter or header
        the caller controls.
        """
        return cls(
            actor_id=user_id,
            actor_role=role or "UNKNOWN",
            source=ActorSource.AUTHENTICATED_SESSION,
        )

    @classmethod
    def system(cls, component: str) -> AuditActor:
        """The application acting on its own behalf, naming the component."""
        return cls(actor_id=f"system:{component}", actor_role="SYSTEM", source=ActorSource.SYSTEM)

    @classmethod
    def unauthenticated(cls, claimed_identifier: str | None = None) -> AuditActor:
        """An act performed with no valid session.

        Any identifier here is a *claim* made by the caller - a username typed
        into a failed login, for instance. It is recorded because it is useful
        for detecting credential stuffing, and it is marked ``UNAUTHENTICATED``
        so it can never be read as a proven identity.
        """
        claimed = (claimed_identifier or "").strip()
        return cls(
            actor_id=f"unauthenticated:{claimed}" if claimed else "unauthenticated",
            actor_role="NONE",
            source=ActorSource.UNAUTHENTICATED,
        )

    def to_canonical(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "source": self.source.value,
        }


def _reject_secret_field_names(metadata: dict[str, Any]) -> None:
    """Refuse metadata whose field names suggest secret material.

    Shares ``FORBIDDEN_FIELD_PATTERNS`` with evidence on purpose: one list, so
    a pattern added for one retained artefact protects the other automatically.
    """
    for name in metadata:
        lowered = name.lower()
        for pattern in FORBIDDEN_FIELD_PATTERNS:
            if pattern in lowered:
                raise AuditError(
                    f"Audit metadata field {name!r} matches forbidden pattern "
                    f"{pattern!r}. The audit log is retained and exported; a "
                    "secret written into it cannot be withdrawn."
                )


def new_audit_id() -> str:
    return f"aud_{uuid.uuid4().hex[:16]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AuditRecord:
    """One append-only entry in the audit log.

    ``sequence`` is assigned by the log, not by the caller, and is contiguous
    from 1. It is part of the canonical bytes, so removing an entry from the
    middle of the log cannot be hidden: the successor's recorded predecessor
    digest stops matching, and the gap in sequence is itself visible.
    """

    audit_id: str
    sequence: int
    event_type: AuditEventType
    outcome: AuditOutcome
    actor: AuditActor
    occurred_at: datetime
    operation_id: str | None = None
    target_identity: str | None = None
    #: Identifier of the evidence record this act produced, when it produced
    #: one. A *reference*, never a copy: audit does not restate evidence.
    evidence_id: str | None = None
    certificate_id: str | None = None
    #: Short statement of the act, chosen by the server. Never free-form caller
    #: input, which would make the log a channel for injected text.
    summary: str = ""
    safe_metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = AUDIT_SCHEMA_VERSION
    canonicalization_version: str = CANONICALIZATION_VERSION
    previous_audit_id: str | None = None
    previous_audit_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.audit_id:
            raise AuditError("audit_id is required")
        if self.sequence < 1:
            raise AuditError("sequence is 1-based; a record numbered below 1 cannot exist")
        if self.occurred_at.tzinfo is None:
            raise AuditError(
                "occurred_at must be timezone-aware; a naive timestamp cannot be "
                "ordered against records written in another zone"
            )
        _reject_secret_field_names(self.safe_metadata)
        if self.previous_audit_digest is not None and not _HEX64.match(self.previous_audit_digest):
            raise AuditError("previous_audit_digest must be 64 lowercase hex characters")
        # A link is only a link if both halves are present.
        if bool(self.previous_audit_id) != bool(self.previous_audit_digest):
            raise AuditError(
                "previous_audit_id and previous_audit_digest must be set together; "
                "a reference without a digest cannot be verified"
            )
        # The genesis record is exactly sequence 1, and only sequence 1.
        if self.sequence == 1 and self.previous_audit_id is not None:
            raise AuditError("the first record cannot reference a predecessor")
        if self.sequence > 1 and self.previous_audit_id is None:
            raise AuditError(
                f"record at sequence {self.sequence} must reference its predecessor; "
                "an unlinked record after the genesis would leave history unverifiable"
            )

    @property
    def is_genesis(self) -> bool:
        return self.previous_audit_id is None

    def to_canonical_dict(self) -> dict[str, Any]:
        """The exact structure that gets canonicalized and hashed.

        Every security-relevant field is present. A field left out of this
        structure would be unprotected: it could be changed in storage without
        altering the digest, which is precisely the mutation this chain exists
        to detect.
        """
        return {
            "actor": self.actor.to_canonical(),
            "audit_id": self.audit_id,
            "canonicalization_version": self.canonicalization_version,
            "certificate_id": self.certificate_id,
            "evidence_id": self.evidence_id,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at.isoformat(),
            "operation_id": self.operation_id,
            "outcome": self.outcome.value,
            "previous_audit_digest": self.previous_audit_digest,
            "previous_audit_id": self.previous_audit_id,
            "safe_metadata": self.safe_metadata,
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "summary": self.summary,
            "target_identity": self.target_identity,
        }

    def canonical_bytes(self) -> bytes:
        return canonicalize(self.to_canonical_dict())

    def digest(self) -> str:
        """SHA-256 over the canonical bytes. Changes whenever the content does."""
        return canonical_hash(self.to_canonical_dict())


__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "SUPPORTED_AUDIT_SCHEMA_VERSIONS",
    "ActorSource",
    "AuditActor",
    "AuditError",
    "AuditEventType",
    "AuditOutcome",
    "AuditRecord",
    "new_audit_id",
    "utcnow",
]
