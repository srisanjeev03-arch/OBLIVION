"""Storing and reloading evidence records and certificates.

The round-trip has one hard requirement: what comes back must hash to what went
in. A certificate records the digest of its evidence, so if persistence altered
the evidence in any way - reordered a key, dropped a null, changed a timestamp's
representation - every verification after a restart would fail, and it would
look like tampering rather than a storage bug.

That is why the canonical bytes are stored verbatim in ``payload`` and the
digest is re-derived from the reloaded object rather than trusted from the row.
"""

from __future__ import annotations

import json
from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from oblivion.certificate.models import Certificate
from oblivion.core.evidence.record import EvidenceRecord
from oblivion.persistence.models.certificate import (
    CertificateModel,
    EvidenceRecordModel,
)


class CertificateRepository:
    def __init__(self, session: Session):
        self.session = session

    # -- raw helpers -------------------------------------------------------

    def create_evidence_record(
        self,
        evidence_id: str,
        operation_id: str,
        evidence_digest: str,
        payload: str,
        **kwargs: Any,
    ) -> EvidenceRecordModel:
        record = EvidenceRecordModel(
            id=evidence_id,
            operation_id=operation_id,
            evidence_digest=evidence_digest,
            payload=payload,
            **kwargs,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def create_certificate(
        self,
        cert_id: str,
        operation_id: str,
        evidence_digest: str,
        public_key: str,
        signature: str,
        **kwargs: Any,
    ) -> CertificateModel:
        model = CertificateModel(
            id=cert_id,
            operation_id=operation_id,
            evidence_digest=evidence_digest,
            public_key=public_key,
            signature=signature,
            **kwargs,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def get_evidence_record(self, evidence_id: str) -> EvidenceRecordModel | None:
        return self.session.get(EvidenceRecordModel, evidence_id)

    def get_certificate(self, cert_id: str) -> CertificateModel | None:
        return self.session.get(CertificateModel, cert_id)

    # -- domain round-trip -------------------------------------------------

    def save_evidence(self, evidence: EvidenceRecord) -> EvidenceRecordModel:
        """Persist a record, storing the exact bytes that were hashed."""
        return self.create_evidence_record(
            evidence_id=evidence.evidence_id,
            operation_id=evidence.operation_id,
            evidence_digest=evidence.digest(),
            payload=evidence.canonical_bytes().decode("utf-8"),
            schema_version=evidence.schema_version,
            canonicalization_version=evidence.canonicalization_version,
            previous_evidence_id=evidence.previous_evidence_id,
            previous_evidence_digest=evidence.previous_evidence_digest,
            created_at=evidence.created_at,
        )

    def load_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        """Rebuild a record from storage, or None when it is not there."""
        row = self.get_evidence_record(evidence_id)
        if row is None:
            return None
        return EvidenceRecord.from_canonical_dict(json.loads(row.payload))

    def load_evidence_chain(self, operation_id: str) -> list[EvidenceRecord]:
        """Every record for an operation, oldest first.

        Ordered by creation time so the chain verifier sees them in the order
        they were produced. A chain assembled in the wrong order is reported as
        broken, which is the correct outcome rather than a silent pass.
        """
        rows = (
            self.session.execute(
                select(EvidenceRecordModel)
                .where(EvidenceRecordModel.operation_id == operation_id)
                .order_by(EvidenceRecordModel.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [EvidenceRecord.from_canonical_dict(json.loads(r.payload)) for r in rows]

    def save_certificate(self, certificate: Certificate) -> CertificateModel:
        """Persist an issued certificate. Only public material is written."""
        return self.create_certificate(
            cert_id=certificate.certificate_id,
            operation_id=certificate.operation_id,
            evidence_digest=certificate.evidence_digest,
            public_key=certificate.public_key,
            signature=certificate.signature,
            evidence_id=certificate.evidence_id,
            certificate_version=certificate.version,
            canonicalization_version=certificate.canonicalization_version,
            evidence_schema_version=certificate.evidence_schema_version,
            target_identity=certificate.target_identity,
            method=certificate.method,
            result=certificate.result,
            signer_id=certificate.signer_id,
            key_id=certificate.key_id,
            limitations=json.dumps(list(certificate.limitations)),
            issued_at=certificate.issued_at,
        )

    def load_certificate(self, cert_id: str) -> Certificate | None:
        """Rebuild a certificate from storage, or None when it is not there."""
        row = self.get_certificate(cert_id)
        if row is None:
            return None
        return certificate_from_model(row)


def certificate_from_model(row: CertificateModel) -> Certificate:
    """Map a stored row onto the domain object the verifier understands.

    Missing optional columns become empty strings rather than ``None`` so the
    STRUCTURE dimension reports them as absent fields - a legacy row is judged,
    not crashed on.

    ``issued_at`` is normalised back to UTC-aware. SQLite does not retain the
    offset even for ``DateTime(timezone=True)``, so a certificate signed with
    ``...+00:00`` in its payload would reload with a naive timestamp, serialise
    differently, and fail its own signature check - a storage artifact that
    would be indistinguishable from tampering.
    """
    issued_at = row.issued_at
    if issued_at is not None and issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=UTC)

    limitations: tuple[str, ...] = ()
    if row.limitations:
        try:
            parsed = json.loads(row.limitations)
            if isinstance(parsed, list):
                limitations = tuple(str(item) for item in parsed)
        except (TypeError, ValueError):
            limitations = (str(row.limitations),)

    return Certificate(
        certificate_id=row.id,
        operation_id=row.operation_id,
        evidence_id=row.evidence_id or "",
        evidence_digest=row.evidence_digest,
        target_identity=row.target_identity or "",
        method=row.method or "",
        result=row.result or "",
        signer_id=row.signer_id or "",
        key_id=row.key_id or "",
        public_key=row.public_key,
        signature=row.signature,
        issued_at=issued_at,
        version=row.certificate_version,
        canonicalization_version=row.canonicalization_version or "",
        evidence_schema_version=row.evidence_schema_version or "",
        limitations=limitations,
    )


__all__ = ["CertificateRepository", "certificate_from_model"]
