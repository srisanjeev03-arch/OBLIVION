"""EvidenceRecord and Certificate models."""
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from oblivion.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceRecordModel(Base):
    """Persisted canonical evidence package (the signed payload, no plaintext content)."""
    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), ForeignKey("operations.id"), nullable=False, index=True)
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CertificateModel(Base):
    """Persisted certificate with embedded public key and signature."""
    __tablename__ = "certificates"
    __table_args__ = (Index("ix_certificates_operation", "operation_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(64), ForeignKey("operations.id"), nullable=False, index=True)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("evidence_records.id"), index=True)
    certificate_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    signing_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="Ed25519")
    key_id: Mapped[Optional[str]] = mapped_column(String(128))
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    claim: Mapped[Optional[str]] = mapped_column(Text)
    limitations: Mapped[Optional[str]] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
