"""EvidenceRecord and Certificate tables.

These store the *public* halves of the evidence/certificate model: the canonical
payload, its digest, and the signature over it. No private key, no bearer token
and no recovery secret is stored here or anywhere reachable from here - evidence
and certificates are made to be handed to third parties, so anything secret that
reached them could never be withdrawn.
"""
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from oblivion.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EvidenceRecordModel(Base):
    """A persisted evidence document: the canonical payload plus its digest."""

    __tablename__ = "evidence_records"
    __table_args__ = (Index("ix_evidence_records_previous", "previous_evidence_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("operations.id"), nullable=False, index=True
    )
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    #: Which canonical byte form produced ``evidence_digest``. Without this a
    #: future codec change would silently reinterpret an existing digest.
    canonicalization_version: Mapped[str | None] = mapped_column(String(32))
    #: The canonical JSON payload, exactly as hashed and signed.
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    #: Chain linkage. Both are set together or neither is.
    previous_evidence_id: Mapped[str | None] = mapped_column(String(64))
    previous_evidence_digest: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class CertificateModel(Base):
    """A persisted certificate.

    ``public_key`` is the signer's *public* key - a claim about who signed,
    which the verifier checks against its own TrustStore. The private key never
    appears in this table.
    """

    __tablename__ = "certificates"
    __table_args__ = (
        Index("ix_certificates_operation", "operation_id"),
        Index("ix_certificates_signer", "signer_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("operations.id"), nullable=False, index=True
    )
    evidence_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("evidence_records.id"), index=True
    )
    certificate_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="1.0"
    )
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Recorded so a verifier knows which codec the signature was produced over.
    canonicalization_version: Mapped[str | None] = mapped_column(String(32))
    evidence_schema_version: Mapped[str | None] = mapped_column(String(32))
    #: What the certificate is about, so a verifier can compare it against an
    #: independently supplied expectation.
    target_identity: Mapped[str | None] = mapped_column(String(1024))
    method: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str | None] = mapped_column(String(32))
    #: The signer identity a TrustStore is keyed by. Confers nothing by itself.
    signer_id: Mapped[str | None] = mapped_column(String(128), index=True)
    signing_algorithm: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Ed25519"
    )
    key_id: Mapped[str | None] = mapped_column(String(128))
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    claim: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
