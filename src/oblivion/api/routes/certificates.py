"""Certificate endpoints."""
import binascii
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import get_db, require_permission
from oblivion.api.schemas.certificate import (
    CertificateOut,
    CertificateVerificationOut,
    DimensionResultOut,
)
from oblivion.certificate.models import Certificate
from oblivion.certificate.verification import verify_certificate
from oblivion.core.evidence.models import EvidencePackage
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.certificate_repo import CertificateRepository

router = APIRouter(prefix="/api/certificates", tags=["certificates"])


@router.get("/{certificate_id}", response_model=CertificateOut, status_code=status.HTTP_200_OK)
async def get_certificate(
    certificate_id: str,
    current_user: UserModel = Depends(require_permission("evidence.view")),
    db: Session = Depends(get_db),
) -> CertificateOut:
    """Retrieve an issued certificate (requires evidence.view permission, no private key exposure)."""
    repo = CertificateRepository(db)
    cert = repo.get_certificate(certificate_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "CERTIFICATE_NOT_FOUND", "message": f"Certificate '{certificate_id}' not found"},
        )
    return CertificateOut.model_validate(cert)


@router.post("/{certificate_id}/verify", response_model=CertificateVerificationOut, status_code=status.HTTP_200_OK)
async def verify_certificate_endpoint(
    certificate_id: str,
    current_user: UserModel = Depends(require_permission("evidence.verify")),
    db: Session = Depends(get_db),
) -> CertificateVerificationOut:
    """
    Verify certificate authenticity, evidence hash, and Ed25519 signature.
    Requires evidence.verify permission.
    Reports dimension-level results for explicit security status.
    """
    repo = CertificateRepository(db)
    cert_model = repo.get_certificate(certificate_id)
    if not cert_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "CERTIFICATE_NOT_FOUND", "message": f"Certificate '{certificate_id}' not found"},
        )

    # Reconstruct the persisted bindings.  The embedded key is only a binding;
    # it is not a trust decision.
    cert_dataclass = Certificate(
        certificate_id=cert_model.id,
        evidence_id=cert_model.evidence_id or "unknown",
        evidence_hash=cert_model.evidence_digest,
        signature=cert_model.signature,
        signer_id=cert_model.key_id or "default",
        timestamp=cert_model.issued_at,
        version=cert_model.certificate_version,
        operation_id=cert_model.operation_id,
        public_key=cert_model.public_key,
    )

    # 2. Retrieve Evidence record if exists
    evidence_pkg = None
    if cert_model.evidence_id:
        ev_record = repo.get_evidence_record(cert_model.evidence_id)
        if ev_record:
            try:
                evidence_dict = json.loads(ev_record.payload)
                import datetime
                evidence_pkg = EvidencePackage(
                    operation_id=evidence_dict.get("operation_id", ""),
                    target_identity=evidence_dict.get("target_identity", ""),
                    target_hash=evidence_dict.get("target_hash", ""),
                    storage_profile=evidence_dict.get("storage_profile", {}),
                    policy=evidence_dict.get("policy", {}),
                    start_timestamp=datetime.datetime.fromisoformat(evidence_dict.get("start_timestamp", datetime.datetime.now().isoformat())),
                    end_timestamp=datetime.datetime.fromisoformat(evidence_dict.get("end_timestamp", datetime.datetime.now().isoformat())),
                    operation_results=evidence_dict.get("operation_results", {}),
                    recovery_test_result=evidence_dict.get("recovery_test_result", {}),
                    residual_scan_result=evidence_dict.get("residual_scan_result", {}),
                    assurance_result=evidence_dict.get("assurance_result", {}),
                    warnings=evidence_dict.get("warnings", []),
                    software_version=evidence_dict.get("software_version", "1.0.0"),
                )
            except Exception:
                # evidence_pkg remains None, verify_certificate will handle it
                pass

    # 3. Perform Dimension-Based Verification
    try:
        pubkey_bytes = binascii.unhexlify(cert_model.public_key)
    except (binascii.Error, ValueError, TypeError):
        # The verifier reports a deterministic FAIL for malformed persisted
        # keys; verification must not become a 500 response.
        pubkey_bytes = b""
    res = verify_certificate(cert_dataclass, evidence_pkg, pubkey_bytes)

    # 4. Map to API Schema
    return CertificateVerificationOut(
        certificate_id=res.certificate_id,
        overall_status=res.overall_status,
        dimensions=[
            DimensionResultOut(
                dimension=d.dimension.value,
                result=d.result.value,
                detail=d.detail,
                evidence_ref=d.evidence_ref
            ) for d in res.dimensions
        ],
        signature_valid=res.signature_valid,
        evidence_integrity=res.evidence_integrity,
        signer_trusted=res.signer_trusted,
        cannot_prove=res.cannot_prove
    )
