"""Certificate endpoints.

Verification is performed entirely server-side. The request body carries only
the caller's *expectations*; every fact that could make a certificate look
valid - the evidence, the trust anchors, the recomputed digest - is loaded by
the server from its own storage and configuration.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import (
    get_db,
    get_trust_store,
    require_permission,
    resolve_audit_actor,
)
from oblivion.api.schemas.certificate import (
    CertificateOut,
    CertificateVerificationOut,
    CertificateVerificationRequest,
    DimensionResultOut,
)
from oblivion.certificate.trust_model import TrustStore
from oblivion.core.audit import AuditEventType, AuditLog, AuditOutcome
from oblivion.certificate.verification import VerificationContext, verify_certificate
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.certificate_repo import CertificateRepository

router = APIRouter(prefix="/api/certificates", tags=["certificates"])


@router.get(
    "/{certificate_id}", response_model=CertificateOut, status_code=status.HTTP_200_OK
)
async def get_certificate(
    certificate_id: str,
    current_user: UserModel = Depends(require_permission("evidence.view")),
    db: Session = Depends(get_db),
) -> CertificateOut:
    """Retrieve an issued certificate (requires evidence.view).

    Returns the signer's public key only; no private key exists in this API.
    """
    repo = CertificateRepository(db)
    cert = repo.get_certificate(certificate_id)
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "CERTIFICATE_NOT_FOUND",
                "message": f"Certificate '{certificate_id}' not found",
            },
        )
    return CertificateOut.model_validate(cert)


@router.post(
    "/{certificate_id}/verify",
    response_model=CertificateVerificationOut,
    status_code=status.HTTP_200_OK,
)
async def verify_certificate_endpoint(
    certificate_id: str,
    request: CertificateVerificationRequest | None = None,
    current_user: UserModel = Depends(require_permission("evidence.verify")),
    trust_store: TrustStore = Depends(get_trust_store),
    db: Session = Depends(get_db),
) -> CertificateVerificationOut:
    """Verify a certificate across ten independent dimensions.

    The caller may supply the operation and target it *expects* this certificate
    to attest to. It cannot supply the outcome: signer trust comes from the
    server's TrustStore, and evidence integrity is recomputed from the stored
    evidence. A request that supplies no expectations gets ``INCONCLUSIVE``,
    which is the truthful answer when nothing independent was available to check
    against.
    """
    repo = CertificateRepository(db)
    certificate = repo.load_certificate(certificate_id)
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "CERTIFICATE_NOT_FOUND",
                "message": f"Certificate '{certificate_id}' not found",
            },
        )

    # Evidence and chain are loaded by the server. A malformed stored payload is
    # reported through the dimensions as unavailable evidence rather than a 500.
    evidence = None
    if certificate.evidence_id:
        try:
            evidence = repo.load_evidence(certificate.evidence_id)
        except Exception:
            evidence = None

    chain: tuple[Any, ...] = ()
    try:
        chain = tuple(repo.load_evidence_chain(certificate.operation_id))
    except Exception:
        chain = ()

    expectations = request or CertificateVerificationRequest()
    context = VerificationContext(
        trust_store=trust_store,
        evidence=evidence,
        evidence_chain=chain or None,
        expected_operation_id=expectations.expected_operation_id,
        expected_target_identity=expectations.expected_target_identity,
    )

    result = verify_certificate(certificate, context)

    # Who asked, which certificate, and what the server answered. The outcome
    # records that the *verification ran*, not that the certificate was valid -
    # the verdict itself is `overall_status` in the metadata. Collapsing the two
    # would make a routine INVALID look like a failed request.
    AuditLog(db).append(
        AuditEventType.CERTIFICATE_VERIFIED,
        AuditOutcome.SUCCEEDED,
        resolve_audit_actor(current_user, db),
        operation_id=certificate.operation_id,
        certificate_id=certificate_id,
        evidence_id=certificate.evidence_id,
        summary=f"Verified certificate; result {result.overall_status}.",
        safe_metadata={
            "overall_status": str(result.overall_status),
            "signer_trusted": bool(result.signer_trusted),
            "signature_valid": bool(result.signature_valid),
            "expected_operation_id": expectations.expected_operation_id,
            "expected_target_identity": expectations.expected_target_identity,
        },
    )

    return CertificateVerificationOut(
        certificate_id=result.certificate_id,
        overall_status=result.overall_status,
        dimensions=[
            DimensionResultOut(
                dimension=item.dimension.value,
                result=item.result.value,
                detail=item.detail,
                evidence_ref=item.evidence_ref,
            )
            for item in result.dimensions
        ],
        cannot_prove=list(result.cannot_prove),
        certificate_version=result.certificate_version,
        verifier_version=result.verifier_version,
        verified_at=result.verified_at,
        signature_valid=result.signature_valid,
        evidence_integrity=result.evidence_integrity,
        signer_trusted=result.signer_trusted,
    )
