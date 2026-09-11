"""Response shapes for the audit endpoints.

Every field a verifier needs in order to *re-check the chain itself* is
exposed: the digest, the predecessor reference and the predecessor digest. A
reader given only the server's verdict has to take the server's word for it; a
reader given the links can recompute them.

The verification response carries ``proves`` and ``does_not_prove`` verbatim
from the core result. The second list is not decoration - it is what stops a
consumer from rendering "audit chain intact" as though it meant the erasure was
sound.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEventOut(BaseModel):
    """One audit record as published."""

    audit_id: str
    sequence: int
    event_type: str
    outcome: str

    #: Server-derived. ``actor_source`` says whether this identity was proven by
    #: a session lookup (AUTHENTICATED_SESSION), asserted by the application
    #: about itself (SYSTEM), or merely claimed (UNAUTHENTICATED).
    actor_id: str
    actor_role: str
    actor_source: str

    operation_id: str | None = None
    target_identity: str | None = None
    evidence_id: str | None = None
    certificate_id: str | None = None
    summary: str = ""
    safe_metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime

    #: The chain fields, published so a client can verify independently.
    digest: str
    previous_audit_id: str | None = None
    previous_audit_digest: str | None = None


class AuditEventPageOut(BaseModel):
    """A page of audit records, oldest first.

    ``total_records`` is the height of the whole log, not the size of this
    page, so a reader can tell a page is a window without inferring it from the
    page happening to be full.
    """

    events: list[AuditEventOut]
    returned: int
    total_records: int
    #: Rows predating the chain. They are not returned in `events` and this
    #: count is how their existence is disclosed instead of silently dropped.
    records_predating_chain: int = 0
    limit: int
    offset: int


class AuditLinkOut(BaseModel):
    audit_id: str
    sequence: int
    #: VALID_GENESIS | VALID_PREDECESSOR | MISSING_PREDECESSOR |
    #: BROKEN_PREDECESSOR | MUTATED_EVENT
    status: str
    detail: str


class AuditChainVerificationOut(BaseModel):
    """The result of verifying the persisted audit chain."""

    #: INTACT | BROKEN | UNVERIFIABLE
    status: str
    checked: int
    reason: str
    links: list[AuditLinkOut]
    first_invalid_audit_id: str | None = None

    #: Rows written before this build's chaining existed. Excluded from the
    #: verdict and reported here, so the part of the log outside the
    #: guarantee is visible rather than merely absent.
    records_predating_chain: int = 0

    #: What an INTACT result establishes. Empty unless the status is INTACT.
    proves: list[str]
    #: Claims this verification never supports, at any status. Always present.
    does_not_prove: list[str]

    #: Restated in the payload so a consumer cannot present audit-chain
    #: integrity as evidence integrity by leaving the distinction out.
    scope_note: str = (
        "This result describes the integrity of the audit log only. It is not a "
        "statement about evidence integrity, erasure success, or certificate "
        "trust, each of which is verified separately against its own artefact."
    )


class AuditVerifyRequest(BaseModel):
    """Optional narrowing for a verification request.

    Supplying ``operation_id`` narrows which records are examined. It cannot
    make a window look complete: a subset that does not begin at the genesis
    record is reported ``UNVERIFIABLE``, because the chain spans every event in
    the system and a per-operation slice necessarily has history before it.
    """

    operation_id: str | None = None
