"""Baseline, RecoveryTest, ResidualFinding, AssuranceResult models."""
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from oblivion.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaselineModel(Base):
    __tablename__ = "baselines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), ForeignKey("operations.id"), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), ForeignKey("targets.id"), nullable=False, index=True)
    file_inventory: Mapped[Optional[str]] = mapped_column(Text)
    hashes: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class RecoveryTestModel(Base):
    __tablename__ = "recovery_tests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), ForeignKey("operations.id"), nullable=False, index=True)
    result_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    evidence_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ResidualFindingModel(Base):
    __tablename__ = "residual_findings"
    __table_args__ = (Index("ix_residual_findings_severity", "severity"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), ForeignKey("operations.id"), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(1024))
    evidence_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AssuranceResultModel(Base):
    __tablename__ = "assurance_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), ForeignKey("operations.id"), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[Optional[str]] = mapped_column(Text)
    limitations: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
