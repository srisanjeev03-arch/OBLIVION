"""Audit endpoints: read the log, and verify it.

Two operations, and deliberately no third. There is no update route and no
delete route, so "append-only from the application perspective" is a property
of the surface area rather than a promise about how the handlers behave.

Both operations are themselves audited. Reading an audit log is a privileged
act - it discloses who did what and when - and a log that cannot answer "who
read this" is missing exactly the events an insider would want hidden. The
access record is written *before* the response is built, so a query that later
fails to serialise has still been recorded.

Authorization is server-side and role-derived: ``audit.view`` and
``audit.verify`` are granted only to ADMIN and AUDITOR by
``core/auth/rbac.py``. Nothing about the caller's role is taken from the
request.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import get_db, require_permission, resolve_audit_actor
from oblivion.api.schemas.audit import (
    AuditChainVerificationOut,
    AuditEventOut,
    AuditEventPageOut,
    AuditLinkOut,
    AuditVerifyRequest,
)
from oblivion.core.audit import (
    AuditActor,
    AuditError,
    AuditEventType,
    AuditLog,
    AuditOutcome,
    AuditQuery,
    StoredAuditRecord,
)
from oblivion.persistence.models.user import UserModel

router = APIRouter(prefix="/api/audit", tags=["audit"])

#: Hard ceiling on a page. A caller cannot ask for the whole log in one
#: response and turn a read into a denial of service against the database.
_MAX_PAGE = 500


def _to_out(entry: StoredAuditRecord) -> AuditEventOut:
    record = entry.record
    return AuditEventOut(
        audit_id=record.audit_id,
        sequence=record.sequence,
        event_type=record.event_type.value,
        outcome=record.outcome.value,
        actor_id=record.actor.actor_id,
        actor_role=record.actor.actor_role,
        actor_source=record.actor.source.value,
        operation_id=record.operation_id,
        target_identity=record.target_identity,
        evidence_id=record.evidence_id,
        certificate_id=record.certificate_id,
        summary=record.summary,
        safe_metadata=record.safe_metadata,
        occurred_at=record.occurred_at,
        digest=entry.stored_digest,
        previous_audit_id=record.previous_audit_id,
        previous_audit_digest=record.previous_audit_digest,
    )


@router.get("/events", response_model=AuditEventPageOut, status_code=status.HTTP_200_OK)
async def list_audit_events(
    operation_id: str | None = Query(None),
    actor_id: str | None = Query(None),
    event_type: str | None = Query(None),
    outcome: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=_MAX_PAGE),
    offset: int = Query(0, ge=0),
    current_user: UserModel = Depends(require_permission("audit.view")),
    db: Session = Depends(get_db),
) -> AuditEventPageOut:
    """Read audit records, oldest first (requires ``audit.view``).

    Unrecognised filter values are rejected with 422 rather than ignored. A
    filter that is silently dropped returns *more* than was asked for while
    looking like it returned exactly what was asked for - in an audit context,
    a way to miss the record you were told to find.
    """
    parsed_event_type: AuditEventType | None = None
    if event_type is not None:
        try:
            parsed_event_type = AuditEventType(event_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "UNKNOWN_EVENT_TYPE",
                    "message": f"'{event_type}' is not a recorded audit event type",
                },
            ) from None

    parsed_outcome: AuditOutcome | None = None
    if outcome is not None:
        try:
            parsed_outcome = AuditOutcome(outcome)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "UNKNOWN_OUTCOME",
                    "message": f"'{outcome}' is not a recorded audit outcome",
                },
            ) from None

    log = AuditLog(db)
    try:
        entries = log.query_stored(
            AuditQuery(
                operation_id=operation_id,
                actor_id=actor_id,
                event_type=parsed_event_type,
                outcome=parsed_outcome,
                since=since,
                until=until,
                limit=limit,
                offset=offset,
            )
        )
        total = log.count()
        legacy = log.count_predating_chain()
    except AuditError as exc:
        # An unreadable row is a finding, not a blank page.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "AUDIT_RECORD_UNREADABLE", "message": str(exc)},
        ) from None

    # The read is itself an act. Recorded before the response is built.
    log.append(
        AuditEventType.AUDIT_LOG_QUERIED,
        AuditOutcome.SUCCEEDED,
        resolve_audit_actor(current_user, db),
        operation_id=operation_id,
        summary=f"Queried the audit log; {len(entries)} record(s) returned.",
        safe_metadata={
            "filter_operation_id": operation_id,
            "filter_actor_id": actor_id,
            "filter_event_type": parsed_event_type.value if parsed_event_type else None,
            "filter_outcome": parsed_outcome.value if parsed_outcome else None,
            "limit": limit,
            "offset": offset,
        },
    )

    return AuditEventPageOut(
        events=[_to_out(entry) for entry in entries],
        returned=len(entries),
        total_records=total,
        records_predating_chain=legacy,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/verify", response_model=AuditChainVerificationOut, status_code=status.HTTP_200_OK
)
async def verify_audit_chain_endpoint(
    request: AuditVerifyRequest | None = None,
    current_user: UserModel = Depends(require_permission("audit.verify")),
    db: Session = Depends(get_db),
) -> AuditChainVerificationOut:
    """Verify the persisted audit chain (requires ``audit.verify``).

    Records are loaded from storage and rehashed. The caller supplies no
    digests, no records and no expected outcome - there is no field in this
    request in which to assert that the log is intact, which is what keeps the
    answer the server's rather than the caller's.
    """
    narrowing = request or AuditVerifyRequest()
    log = AuditLog(db)

    try:
        result = log.verify(operation_id=narrowing.operation_id)
    except AuditError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "AUDIT_RECORD_UNREADABLE", "message": str(exc)},
        ) from None

    actor: AuditActor = resolve_audit_actor(current_user, db)
    log.append(
        AuditEventType.AUDIT_LOG_VERIFIED,
        AuditOutcome.SUCCEEDED,
        actor,
        operation_id=narrowing.operation_id,
        summary=f"Verified the audit chain; result {result.status.value}.",
        safe_metadata={
            "chain_status": result.status.value,
            "records_checked": result.checked,
        },
    )

    return AuditChainVerificationOut(
        status=result.status.value,
        checked=result.checked,
        reason=result.reason,
        links=[
            AuditLinkOut(
                audit_id=link.audit_id,
                sequence=link.sequence,
                status=link.status.value,
                detail=link.detail,
            )
            for link in result.links
        ],
        first_invalid_audit_id=result.first_invalid_audit_id,
        records_predating_chain=result.records_predating_chain,
        proves=list(result.proves),
        does_not_prove=list(result.does_not_prove),
    )
