"""Audit event storage.

## Why the hashed fields are stored as text

``occurred_at`` and ``safe_metadata`` are part of the canonical bytes that
produce a record's digest, so they must come back out of the database as
*exactly* what went in. Two storage choices would quietly break that:

* A ``DateTime`` column under SQLite does not preserve ``tzinfo``. A record
  written as ``...+00:00`` would reload naive, its ``isoformat()`` would differ
  by six characters, and every reloaded record would hash differently from the
  digest stored beside it - reporting the entire log as ``MUTATED_EVENT``. A
  tamper detector that fires on every honest row is worse than none, because it
  trains its reader to ignore it.
* ``str(dict)`` - the Python repr, which the previous revision used - is not
  parseable back into a dict at all, so the metadata could never be rehashed.

Both are therefore stored as text in their canonical form: the ISO-8601 string
that was hashed, and the ``OBLIVION-CANON-1`` JSON encoding of the metadata.
Normalising timestamps to UTC before writing also makes the column sort and
range-filter correctly as a string.

``created_at`` is kept separately and is *not* hashed: it is the moment the row
reached the database, useful operationally, and deliberately distinct from the
moment the act occurred.
"""
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from oblivion.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditEventModel(Base):
    """One append-only audit entry.

    Append-only is enforced above this class, in ``core/audit/log.py`` and in
    the routes: there is no update or delete path through the API. The model
    itself carries the chain fields that make a violation *detectable* if one
    ever happens below the application - directly in the database file, say.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_actor_time", "actor_id", "created_at"),
        Index("ix_audit_event_type", "event_type"),
        Index("ix_audit_sequence", "sequence", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    #: 1-based, contiguous, assigned by the log. Unique so that two concurrent
    #: appends cannot both claim the same position: one of them fails and
    #: retries rather than silently forking history.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)

    #: Server-derived. ``actor_source`` records whether this identity was proven
    #: by a session lookup or is merely a claim, so the two can never be read as
    #: the same thing.
    actor_id: Mapped[str | None] = mapped_column(String(128), index=True)
    actor_role: Mapped[str | None] = mapped_column(String(128))
    actor_source: Mapped[str | None] = mapped_column(String(32))

    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    target_id: Mapped[str | None] = mapped_column(String(1024), index=True)
    evidence_id: Mapped[str | None] = mapped_column(String(64), index=True)
    certificate_id: Mapped[str | None] = mapped_column(String(64), index=True)

    summary: Mapped[str | None] = mapped_column(Text)

    #: Canonical JSON. Never a Python repr - see the module docstring.
    safe_metadata: Mapped[str | None] = mapped_column(Text)

    #: The canonical ISO-8601 instant that was hashed, normalised to UTC.
    occurred_at: Mapped[str | None] = mapped_column(String(64), index=True)

    schema_version: Mapped[str | None] = mapped_column(String(32))
    canonicalization_version: Mapped[str | None] = mapped_column(String(32))

    #: SHA-256 over the canonical bytes, as computed at append time.
    #: Verification recomputes from the stored content and compares against this
    #: value, so this column must never be rewritten.
    digest: Mapped[str | None] = mapped_column(String(64))

    previous_audit_id: Mapped[str | None] = mapped_column(String(64))
    previous_audit_digest: Mapped[str | None] = mapped_column(String(64))

    #: When the row reached the database. Not part of the digest.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
