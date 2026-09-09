"""Target, Operation, OperationEvent models."""
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oblivion.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TargetModel(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    canonical_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_count: Mapped[int | None] = mapped_column(Integer)
    total_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    storage_profile_id: Mapped[str | None] = mapped_column(String(64), index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    operations: Mapped[list["OperationModel"]] = relationship(back_populates="target")


class OperationModel(Base):
    __tablename__ = "operations"
    __table_args__ = (Index("ix_operations_state", "state"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_id: Mapped[str] = mapped_column(String(64), ForeignKey("targets.id"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str | None] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED")
    actor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    requested_by: Mapped[str | None] = mapped_column(String(64), index=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), index=True)
    executed_by: Mapped[str | None] = mapped_column(String(64), index=True)
    verified_by: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    warnings: Mapped[str | None] = mapped_column(Text)


    target: Mapped["TargetModel"] = relationship(back_populates="operations")
    events: Mapped[list["OperationEventModel"]] = relationship(
        back_populates="operation", cascade="all, delete-orphan", order_by="OperationEventModel.sequence"
    )


class OperationEventModel(Base):
    """Append-only event log for state transitions and key lifecycle points."""
    __tablename__ = "operation_events"
    __table_args__ = (Index("ix_operation_events_op_seq", "operation_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), ForeignKey("operations.id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str | None] = mapped_column(String(32))
    payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    operation: Mapped["OperationModel"] = relationship(back_populates="events")
