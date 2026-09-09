"""Certificate repository."""
from typing import Optional, Any
from sqlalchemy.orm import Session
from oblivion.persistence.models.certificate import EvidenceRecordModel, CertificateModel


class CertificateRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_evidence_record(self, evidence_id: str, operation_id: str, evidence_digest: str, payload: str, **kwargs: Any) -> EvidenceRecordModel:
        e = EvidenceRecordModel(
            id=evidence_id, operation_id=operation_id, evidence_digest=evidence_digest, payload=payload, **kwargs
        )
        self.session.add(e)
        self.session.flush()
        return e

    def create_certificate(self, cert_id: str, operation_id: str, evidence_digest: str, public_key: str, signature: str, **kwargs: Any) -> CertificateModel:
        c = CertificateModel(
            id=cert_id, operation_id=operation_id, evidence_digest=evidence_digest,
            public_key=public_key, signature=signature, **kwargs
        )
        self.session.add(c)
        self.session.flush()
        return c

    def get_evidence_record(self, evidence_id: str) -> Optional[EvidenceRecordModel]:
        return self.session.get(EvidenceRecordModel, evidence_id)

    def get_certificate(self, cert_id: str) -> Optional[CertificateModel]:
        return self.session.get(CertificateModel, cert_id)
