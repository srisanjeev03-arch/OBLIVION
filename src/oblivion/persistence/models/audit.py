"""Audit event model."""
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from oblivion.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AuditEventModel(Base):
    """Append-only audit log. No sensitive plaintext content stored."""
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_actor_time", "actor_id", "created_at"),
        Index("ix_audit_event_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), index=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_metadata: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
