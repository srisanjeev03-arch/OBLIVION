"""Appending to, reading and verifying the audit log.

## Two ways to append, and why both are needed

``append`` joins the caller's transaction. ``append_independently`` opens its
own session and commits immediately. The choice is not a performance question,
it is a correctness one.

A success entry must share the caller's transaction. Writing
``OPERATION_CREATED / SUCCEEDED`` and then letting the operation insert fail
would leave the log asserting an act that never happened - a false record,
which is worse than a missing one.

A *refusal* entry must not. "This principal was denied" is a fact about
something that really occurred, and the request that produced it is about to
raise and roll back. An entry written inside that transaction would be undone,
so the log would fall silent about exactly the events most worth keeping:
denied access, rejected approvals, failed logins. Those go through
``append_independently``.

## Sequence assignment

The next sequence is read from the persisted tail, not from an in-memory
counter, so a restart cannot restart the numbering and fork history. The
``sequence`` column is unique, so if two appends race, one loses the insert and
retries against the new tail rather than both claiming the same position.

## Failures are never swallowed

The previous revision ended its audit write with ``except Exception: pass``. A
log that silently declines to record is indistinguishable from a log with
nothing to record, and that difference is the whole value of the artefact.
:class:`AuditAppendError` is raised instead.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from oblivion.core.evidence.canonicalize import canonical_str
from oblivion.persistence.models.audit import AuditEventModel

from .chain import AuditChainVerification, StoredAuditRecord, verify_audit_chain
from .records import (
    AUDIT_SCHEMA_VERSION,
    ActorSource,
    AuditActor,
    AuditError,
    AuditEventType,
    AuditOutcome,
    AuditRecord,
    new_audit_id,
    utcnow,
)

#: How many times an append retries when it loses a race for a sequence number.
_MAX_SEQUENCE_RETRIES = 5


class AuditAppendError(RuntimeError):
    """Raised when an audit record could not be written.

    Deliberately loud, and deliberately not a subclass of the errors the
    surrounding request handlers treat as routine.
    """


@dataclass(frozen=True)
class AuditQuery:
    """Filters for reading the log. All are optional and combine with AND."""

    operation_id: str | None = None
    actor_id: str | None = None
    event_type: AuditEventType | None = None
    outcome: AuditOutcome | None = None
    #: Inclusive lower bound on ``occurred_at``, as an aware datetime.
    since: datetime | None = None
    #: Exclusive upper bound on ``occurred_at``.
    until: datetime | None = None
    limit: int = 100
    offset: int = 0


def _iso_utc(moment: datetime) -> str:
    """The canonical instant string: always UTC, always aware.

    Normalising here is what lets the stored column be compared and sorted as
    text, and guarantees that the value which gets hashed is the value that
    comes back.
    """
    if moment.tzinfo is None:
        raise AuditError("a naive timestamp cannot be recorded in the audit log")
    return moment.astimezone(UTC).isoformat()


def _record_to_model(record: AuditRecord) -> AuditEventModel:
    return AuditEventModel(
        id=record.audit_id,
        sequence=record.sequence,
        event_type=record.event_type.value,
        outcome=record.outcome.value,
        actor_id=record.actor.actor_id,
        actor_role=record.actor.actor_role,
        actor_source=record.actor.source.value,
        operation_id=record.operation_id,
        target_id=record.target_identity,
        evidence_id=record.evidence_id,
        certificate_id=record.certificate_id,
        summary=record.summary,
        safe_metadata=canonical_str(record.safe_metadata),
        occurred_at=_iso_utc(record.occurred_at),
        schema_version=record.schema_version,
        canonicalization_version=record.canonicalization_version,
        digest=record.digest(),
        previous_audit_id=record.previous_audit_id,
        previous_audit_digest=record.previous_audit_digest,
    )


def _read_metadata(model: AuditEventModel, *, chained: bool) -> dict[str, Any]:
    """Decode a row's metadata, holding chained rows to the strict standard.

    A chained row's metadata is part of its digest, so anything unparseable
    there is genuine corruption and is raised.

    A row written before this build stored metadata as a Python repr, which is
    not JSON and never will be. Refusing to read those would make the whole
    audit log unviewable after an upgrade - punishing the operator for the
    previous revision's format. It is surfaced instead under a key that names
    exactly what it is, so nobody mistakes it for a structured value that was
    hashed.
    """
    raw = model.safe_metadata
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except ValueError:
        if chained:
            raise AuditError(
                f"Audit row {model.id} carries a digest but its metadata is not "
                "readable as canonical JSON; the row is corrupt."
            ) from None
        return {"legacy_unparsed_metadata": raw}
    if not isinstance(decoded, dict):
        if chained:
            raise AuditError(f"audit row {model.id} has non-object metadata")
        return {"legacy_unparsed_metadata": raw}
    return decoded


def _model_to_stored(model: AuditEventModel) -> StoredAuditRecord:
    """Rebuild a record from a row, preserving exactly what was hashed.

    A row that cannot be rebuilt is an error, never a skipped entry: quietly
    dropping an unreadable row would let a tamperer hide an event by corrupting
    it instead of deleting it.
    """
    chained = bool(model.digest)
    try:
        metadata = _read_metadata(model, chained=chained)

        if model.occurred_at is None:
            raise AuditError(f"audit row {model.id} has no occurred_at")

        record = AuditRecord(
            audit_id=model.id,
            sequence=model.sequence,
            event_type=AuditEventType(model.event_type),
            outcome=AuditOutcome(model.outcome),
            actor=AuditActor(
                actor_id=model.actor_id or "",
                actor_role=model.actor_role or "",
                source=ActorSource(model.actor_source or ActorSource.SYSTEM.value),
            ),
            occurred_at=datetime.fromisoformat(model.occurred_at),
            operation_id=model.operation_id,
            target_identity=model.target_id,
            evidence_id=model.evidence_id,
            certificate_id=model.certificate_id,
            summary=model.summary or "",
            safe_metadata=metadata,
            schema_version=model.schema_version or AUDIT_SCHEMA_VERSION,
            canonicalization_version=model.canonicalization_version or "",
            previous_audit_id=model.previous_audit_id,
            previous_audit_digest=model.previous_audit_digest,
        )
    except AuditError:
        raise
    except (ValueError, TypeError) as exc:
        raise AuditError(
            f"Audit row {model.id} could not be read back ({type(exc).__name__}: {exc})"
        ) from None

    return StoredAuditRecord(record=record, stored_digest=model.digest or "")


class AuditLog:
    """Append-only audit log over a SQLAlchemy session.

    There is no ``update`` and no ``delete``. That absence *is* the append-only
    property at the application layer: not a rule written down somewhere, but a
    method that does not exist to be called.
    """

    def __init__(self, session: Session):
        self._session = session

    # -- appending ---------------------------------------------------------

    def _tail(self) -> AuditEventModel | None:
        stmt = select(AuditEventModel).order_by(AuditEventModel.sequence.desc()).limit(1)
        return self._session.execute(stmt).scalars().first()

    def append(
        self,
        event_type: AuditEventType,
        outcome: AuditOutcome,
        actor: AuditActor,
        *,
        operation_id: str | None = None,
        target_identity: str | None = None,
        evidence_id: str | None = None,
        certificate_id: str | None = None,
        summary: str = "",
        safe_metadata: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> AuditRecord:
        """Append one record inside the caller's transaction.

        ``actor`` must have been built by one of :class:`AuditActor`'s named
        constructors from a server-resolved identity. Nothing in this signature
        accepts a caller-supplied actor string, which is what stops a request
        body from choosing who an act is attributed to.
        """
        metadata = dict(safe_metadata or {})
        moment = occurred_at or utcnow()

        last_error: Exception | None = None
        for _ in range(_MAX_SEQUENCE_RETRIES):
            tail = self._tail()
            sequence = (tail.sequence + 1) if tail else 1
            previous_id = tail.id if tail else None
            previous_digest = tail.digest if tail else None

            # A tail without a digest cannot be linked to honestly. Refuse
            # rather than write a record whose predecessor reference is
            # unverifiable by construction.
            if tail is not None and not previous_digest:
                raise AuditAppendError(
                    f"The current tail of the audit log ({tail.id}) carries no digest, "
                    "so a verifiable link to it cannot be formed."
                )

            record = AuditRecord(
                audit_id=new_audit_id(),
                sequence=sequence,
                event_type=event_type,
                outcome=outcome,
                actor=actor,
                occurred_at=moment,
                operation_id=operation_id,
                target_identity=target_identity,
                evidence_id=evidence_id,
                certificate_id=certificate_id,
                summary=summary,
                safe_metadata=metadata,
                previous_audit_id=previous_id,
                previous_audit_digest=previous_digest,
            )

            model = _record_to_model(record)
            self._session.add(model)
            try:
                self._session.flush()
            except IntegrityError as exc:
                # Another append took this sequence. Discard the losing row and
                # re-read the tail; never reuse the position.
                self._session.rollback()
                last_error = exc
                continue
            except SQLAlchemyError as exc:
                raise AuditAppendError(
                    f"The audit record could not be written ({type(exc).__name__}: {exc})"
                ) from exc
            return record

        raise AuditAppendError(
            "The audit record could not be assigned a sequence after "
            f"{_MAX_SEQUENCE_RETRIES} attempts: {last_error}"
        )

    # -- reading -----------------------------------------------------------

    def query(self, query: AuditQuery) -> list[AuditRecord]:
        """Read records oldest-first, subject to the filters."""
        return [entry.record for entry in self.query_stored(query)]

    def count_predating_chain(self) -> int:
        """Rows written before this build's chaining existed.

        Reported alongside every page and every verification, so the part of
        the log outside the guarantee is visible rather than merely absent.
        """
        stmt = (
            select(func.count())
            .select_from(AuditEventModel)
            .where(AuditEventModel.digest.is_(None))
        )
        return int(self._session.execute(stmt).scalar_one())

    def query_stored(self, query: AuditQuery) -> list[StoredAuditRecord]:
        stmt = select(AuditEventModel).where(AuditEventModel.digest.is_not(None))

        if query.operation_id is not None:
            stmt = stmt.where(AuditEventModel.operation_id == query.operation_id)
        if query.actor_id is not None:
            stmt = stmt.where(AuditEventModel.actor_id == query.actor_id)
        if query.event_type is not None:
            stmt = stmt.where(AuditEventModel.event_type == query.event_type.value)
        if query.outcome is not None:
            stmt = stmt.where(AuditEventModel.outcome == query.outcome.value)
        if query.since is not None:
            stmt = stmt.where(AuditEventModel.occurred_at >= _iso_utc(query.since))
        if query.until is not None:
            stmt = stmt.where(AuditEventModel.occurred_at < _iso_utc(query.until))

        stmt = stmt.order_by(AuditEventModel.sequence.asc())
        stmt = stmt.offset(max(0, query.offset)).limit(max(1, query.limit))

        rows = self._session.execute(stmt).scalars().all()
        return [_model_to_stored(row) for row in rows]

    def count(self) -> int:
        """The highest sequence written, which is also the number of records."""
        stmt = (
            select(AuditEventModel.sequence)
            .where(AuditEventModel.digest.is_not(None))
            .order_by(AuditEventModel.sequence.desc())
            .limit(1)
        )
        highest = self._session.execute(stmt).scalars().first()
        return int(highest or 0)

    # -- verifying ---------------------------------------------------------

    def verify(
        self,
        *,
        operation_id: str | None = None,
        limit: int | None = None,
    ) -> AuditChainVerification:
        """Verify the persisted log, loading every record from storage.

        Verification always reads from the database rather than from anything
        held in memory. A verifier that checked its own in-memory copy would
        confirm only that it had not corrupted itself.

        ``operation_id`` narrows the records examined, but it is not a way to
        verify a subset in isolation: the chain links every event in the system,
        so a per-operation view is necessarily a window and is reported as
        ``UNVERIFIABLE`` unless it happens to begin at the genesis record.
        """
        stmt = select(AuditEventModel).where(AuditEventModel.digest.is_not(None))
        if operation_id is not None:
            stmt = stmt.where(AuditEventModel.operation_id == operation_id)
        stmt = stmt.order_by(AuditEventModel.sequence.asc())
        if limit is not None:
            stmt = stmt.limit(max(1, limit))

        rows = self._session.execute(stmt).scalars().all()
        entries: Sequence[StoredAuditRecord] = [_model_to_stored(row) for row in rows]
        result = verify_audit_chain(entries)

        legacy = self.count_predating_chain()
        if not legacy:
            return result
        return replace(
            result,
            records_predating_chain=legacy,
            reason=(
                f"{result.reason} Separately, {legacy} record(s) predate this build's "
                "chaining, carry no digest, and are outside this verification."
            ),
        )


def append_independently(
    session_factory: sessionmaker[Session],
    event_type: AuditEventType,
    outcome: AuditOutcome,
    actor: AuditActor,
    **fields: Any,
) -> AuditRecord:
    """Append in a transaction of its own, committed immediately.

    For acts that really happened but whose request is about to fail: a denied
    authorization, a rejected approval, a failed login. Writing those inside the
    doomed transaction would roll them straight back out again.
    """
    with session_factory() as session:
        log = AuditLog(session)
        record = log.append(event_type, outcome, actor, **fields)
        session.commit()
        return record


__all__ = ["AuditAppendError", "AuditLog", "AuditQuery", "append_independently"]
