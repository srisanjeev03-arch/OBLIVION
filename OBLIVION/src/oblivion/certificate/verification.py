from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field

from .models import Certificate
from .trust import TrustStore, TrustStoreError, TrustedSigner, parse_public_key_bytes
from oblivion.core.evidence.models import EvidencePackage
from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.certificate.integrity import hash_integrity


SUPPORTED_CERTIFICATE_VERSIONS = {"1.0.0"}
SUPPORTED_SIGNING_ALGORITHMS = {"Ed25519"}


class VerificationDimension(str, Enum):
    STRUCTURE = "STRUCTURE"
    VERSION_COMPATIBILITY = "VERSION_COMPATIBILITY"
    EVIDENCE_AVAILABILITY = "EVIDENCE_AVAILABILITY"
    EVIDENCE_DIGEST = "EVIDENCE_DIGEST"
    SIGNATURE_VALIDITY = "SIGNATURE_VALIDITY"
    PUBLIC_KEY_CONSISTENCY = "PUBLIC_KEY_CONSISTENCY"
    SIGNER_TRUST = "SIGNER_TRUST"
    EVIDENCE_CHAIN_INTEGRITY = "EVIDENCE_CHAIN_INTEGRITY"
    OPERATION_CONSISTENCY = "OPERATION_CONSISTENCY"
    TARGET_CONSISTENCY = "TARGET_CONSISTENCY"


class DimensionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_CHECKED = "NOT_CHECKED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class DimensionResult:
    dimension: VerificationDimension
    status: DimensionStatus
    detail: str = ""


@dataclass
class CertificateVerification:
    certificate_id: str
    overall_status: str
    dimensions: List[DimensionResult]
    cannot_prove: List[str]
    certificate_version: str
    verifier_version: str = "0.1.0-slice1"
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: str = ""


@dataclass
class VerificationContext:
    trust_store: Optional[TrustStore] = None
    expected_operation_id: Optional[str] = None
    expected_target_identity: Optional[str] = None
    require_signer_trust: bool = True
    allow_unsigned: bool = False


def _dimension(dimension: VerificationDimension, status: DimensionStatus, detail: str = "") -> DimensionResult:
    return DimensionResult(dimension=dimension, status=status, detail=detail)


def _check_structure(cert: Certificate, evidence: Optional[EvidencePackage]) -> DimensionResult:
    issues = []
    
    if not cert.certificate_id or not cert.certificate_id.strip():
        issues.append("certificate_id is empty")
    
    if not cert.evidence_hash or len(cert.evidence_hash) != 64 or not all(c in "0123456789abcdefABCDEF" for c in cert.evidence_hash):
        issues.append("evidence_hash must be 64 hex characters")
    
    if not cert.signature or not cert.signature.strip():
        issues.append("signature is empty")
    
    if not cert.signer_id or not cert.signer_id.strip():
        issues.append("signer_id is empty")
    
    try:
        datetime.fromisoformat(cert.timestamp.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        issues.append("timestamp is not a valid ISO datetime")
    
    if evidence is None:
        issues.append("evidence is None")
    elif not isinstance(evidence, EvidencePackage):
        issues.append("evidence is not an EvidencePackage instance")
    else:
        if not evidence.operation_id or not evidence.operation_id.strip():
            issues.append("evidence.operation_id is empty")
        if not evidence.target_identity or not evidence.target_identity.strip():
            issues.append("evidence.target_identity is empty")
        if not evidence.target_hash or len(evidence.target_hash) != 64 or not all(c in "0123456789abcdefABCDEF" for c in evidence.target_hash):
            issues.append("evidence.target_hash must be 64 hex characters")
        if not evidence.software_version or not evidence.software_version.strip():
            issues.append("evidence.software_version is empty")
    
    if issues:
        return _dimension(VerificationDimension.STRUCTURE, DimensionStatus.FAIL, "; ".join(issues))
    
    return _dimension(VerificationDimension.STRUCTURE, DimensionStatus.PASS, "All structural checks passed")


def _check_version_compatibility(cert: Certificate) -> DimensionResult:
    if cert.version in SUPPORTED_CERTIFICATE_VERSIONS:
        return _dimension(VerificationDimension.VERSION_COMPATIBILITY, DimensionStatus.PASS, f"Version {cert.version} is supported")
    return _dimension(VerificationDimension.VERSION_COMPATIBILITY, DimensionStatus.FAIL, f"Version {cert.version} is not supported")


def _check_evidence_availability(cert: Certificate, evidence: Optional[EvidencePackage]) -> DimensionResult:
    if evidence is None:
        return _dimension(VerificationDimension.EVIDENCE_AVAILABILITY, DimensionStatus.FAIL, "Evidence is None")
    if not isinstance(evidence, EvidencePackage):
        return _dimension(VerificationDimension.EVIDENCE_AVAILABILITY, DimensionStatus.INCONCLUSIVE, "Evidence is not a valid EvidencePackage")
    return _dimension(VerificationDimension.EVIDENCE_AVAILABILITY, DimensionStatus.PASS, "Evidence is available and valid")


def _check_evidence_digest(cert: Certificate, evidence: Optional[EvidencePackage]) -> DimensionResult:
    if evidence is None:
        return _dimension(VerificationDimension.EVIDENCE_DIGEST, DimensionStatus.INCONCLUSIVE, "Cannot compute digest: evidence is None")
    
    try:
        computed_hash = hash_integrity(evidence)
        if computed_hash == cert.evidence_hash:
            return _dimension(VerificationDimension.EVIDENCE_DIGEST, DimensionStatus.PASS, "Evidence digest matches certificate")
        return _dimension(VerificationDimension.EVIDENCE_DIGEST, DimensionStatus.FAIL, f"Evidence digest mismatch: expected {cert.evidence_hash}, got {computed_hash}")
    except Exception as e:
        return _dimension(VerificationDimension.EVIDENCE_DIGEST, DimensionStatus.INCONCLUSIVE, f"Hashing failed: {e}")


def _check_signature_validity(cert: Certificate, evidence: Optional[EvidencePackage]) -> DimensionResult:
    if evidence is None:
        return _dimension(VerificationDimension.SIGNATURE_VALIDITY, DimensionStatus.INCONCLUSIVE, "Cannot verify signature: evidence is None")
    
    try:
        signature_bytes = bytes.fromhex(cert.signature)
        evidence_hash_bytes = bytes.fromhex(cert.evidence_hash)
        
        public_key_bytes = parse_public_key_bytes(cert.public_key)
        
        verifier = Ed25519SignerVerifier(public_key_bytes)
        is_valid = verifier.verify(evidence_hash_bytes, signature_bytes)
        
        if is_valid:
            return _dimension(VerificationDimension.SIGNATURE_VALIDITY, DimensionStatus.PASS, "Signature is valid")
        return _dimension(VerificationDimension.SIGNATURE_VALIDITY, DimensionStatus.FAIL, "Signature verification failed")
    except ValueError as e:
        return _dimension(VerificationDimension.SIGNATURE_VALIDITY, DimensionStatus.INCONCLUSIVE, f"Hex decoding error: {e}")
    except Exception as e:
        return _dimension(VerificationDimension.SIGNATURE_VALIDITY, DimensionStatus.INCONCLUSIVE, f"Verification error: {e}")


def _check_public_key_consistency(cert: Certificate, context: VerificationContext) -> DimensionResult:
    if context.trust_store is None:
        return _dimension(VerificationDimension.PUBLIC_KEY_CONSISTENCY, DimensionStatus.NOT_CHECKED, "No trust store provided")
    
    try:
        trusted_signer = context.trust_store.get_signer(cert.signer_id)
        if trusted_signer is None:
            return _dimension(VerificationDimension.PUBLIC_KEY_CONSISTENCY, DimensionStatus.FAIL, f"Signer {cert.signer_id} not found in trust store")
        
        cert_public_key = parse_public_key_bytes(cert.public_key)
        if cert_public_key == trusted_signer.public_key:
            return _dimension(VerificationDimension.PUBLIC_KEY_CONSISTENCY, DimensionStatus.PASS, "Public key matches trust store")
        return _dimension(VerificationDimension.PUBLIC_KEY_CONSISTENCY, DimensionStatus.FAIL, "Public key does not match trust store")
    except TrustStoreError as e:
        return _dimension(VerificationDimension.PUBLIC_KEY_CONSISTENCY, DimensionStatus.INCONCLUSIVE, f"Trust store error: {e}")
    except Exception as e:
        return _dimension(VerificationDimension.PUBLIC_KEY_CONSISTENCY, DimensionStatus.INCONCLUSIVE, f"Public key parsing error: {e}")


def _check_signer_trust(cert: Certificate, context: VerificationContext) -> DimensionResult:
    if not context.require_signer_trust:
        return _dimension(VerificationDimension.SIGNER_TRUST, DimensionStatus.NOT_CHECKED, "Signer trust check disabled")
    
    if context.trust_store is None:
        return _dimension(VerificationDimension.SIGNER_TRUST, DimensionStatus.FAIL, "No trust store provided, cannot verify signer trust")
    
    try:
        trusted_signer = context.trust_store.get_signer(cert.signer_id)
        if trusted_signer is None:
            return _dimension(VerificationDimension.SIGNER_TRUST, DimensionStatus.FAIL, f"Signer {cert.signer_id} is not trusted")
        
        cert_public_key = parse_public_key_bytes(cert.public_key)
        if cert_public_key != trusted_signer.public_key:
            return _dimension(VerificationDimension.SIGNER_TRUST, DimensionStatus.FAIL, "Signer public key does not match trust store")
        
        return _dimension(VerificationDimension.SIGNER_TRUST, DimensionStatus.PASS, f"Signer {cert.signer_id} is trusted")
    except TrustStoreError as e:
        return _dimension(VerificationDimension.SIGNER_TRUST, DimensionStatus.FAIL, f"Trust store error: {e}")
    except Exception as e:
        return _dimension(VerificationDimension.SIGNER_TRUST, DimensionStatus.FAIL, f"Signer trust check failed: {e}")


def _check_evidence_chain_integrity(cert: Certificate, evidence: Optional[EvidencePackage]) -> DimensionResult:
    if evidence is None:
        return _dimension(VerificationDimension.EVIDENCE_CHAIN_INTEGRITY, DimensionStatus.INCONCLUSIVE, "Cannot check chain integrity: evidence is None")
    
    if hasattr(cert, 'evidence_id') and cert.evidence_id:
        if cert.evidence_id == evidence.operation_id:
            return _dimension(VerificationDimension.EVIDENCE_CHAIN_INTEGRITY, DimensionStatus.PASS, "Evidence chain integrity verified")
        return _dimension(VerificationDimension.EVIDENCE_CHAIN_INTEGRITY, DimensionStatus.FAIL, f"Evidence chain mismatch: cert.evidence_id={cert.evidence_id}, evidence.operation_id={evidence.operation_id}")
    
    return _dimension(VerificationDimension.EVIDENCE_CHAIN_INTEGRITY, DimensionStatus.PASS, "No evidence_id in certificate, chain check not applicable")


def _check_operation_consistency(cert: Certificate, evidence: Optional[EvidencePackage], context: VerificationContext) -> DimensionResult:
    if context.expected_operation_id is None:
        return _dimension(VerificationDimension.OPERATION_CONSISTENCY, DimensionStatus.NOT_CHECKED, "No expected operation ID provided")
    
    if evidence is None:
        return _dimension(VerificationDimension.OPERATION_CONSISTENCY, DimensionStatus.INCONCLUSIVE, "Cannot check operation consistency: evidence is None")
    
    if evidence.operation_id == context.expected_operation_id:
        return _dimension(VerificationDimension.OPERATION_CONSISTENCY, DimensionStatus.PASS, "Operation ID matches expected")
    return _dimension(VerificationDimension.OPERATION_CONSISTENCY, DimensionStatus.FAIL, f"Operation ID mismatch: expected {context.expected_operation_id}, got {evidence.operation_id}")


def _check_target_consistency(cert: Certificate, evidence: Optional[EvidencePackage], context: VerificationContext) -> DimensionResult:
    if context.expected_target_identity is None:
        return _dimension(VerificationDimension.TARGET_CONSISTENCY, DimensionStatus.NOT_CHECKED, "No expected target identity provided")
    
    if evidence is None:
        return _dimension(VerificationDimension.TARGET_CONSISTENCY, DimensionStatus.INCONCLUSIVE, "Cannot check target consistency: evidence is None")
    
    if evidence.target_identity == context.expected_target_identity:
        return _dimension(VerificationDimension.TARGET_CONSISTENCY, DimensionStatus.PASS, "Target identity matches expected")
    return _dimension(VerificationDimension.TARGET_CONSISTENCY, DimensionStatus.FAIL, f"Target identity mismatch: expected {context.expected_target_identity}, got {evidence.target_identity}")


REQUIRED_DIMENSIONS = {
    VerificationDimension.STRUCTURE,
    VerificationDimension.VERSION_COMPATIBILITY,
    VerificationDimension.EVIDENCE_AVAILABILITY,
    VerificationDimension.EVIDENCE_DIGEST,
    VerificationDimension.SIGNATURE_VALIDITY,
    VerificationDimension.SIGNER_TRUST,
}


def verify_certificate(cert: Certificate, evidence: Optional[EvidencePackage], context: Optional[VerificationContext] = None) -> CertificateVerification:
    if context is None:
        context = VerificationContext()
    
    dimensions = [
        _check_structure(cert, evidence),
        _check_version_compatibility(cert),
        _check_evidence_availability(cert, evidence),
        _check_evidence_digest(cert, evidence),
        _check_signature_validity(cert, evidence),
        _check_public_key_consistency(cert, context),
        _check_signer_trust(cert, context),
        _check_evidence_chain_integrity(cert, evidence),
        _check_operation_consistency(cert, evidence, context),
        _check_target_consistency(cert, evidence, context),
    ]
    
    cannot_prove = []
    has_fail = False
    has_inconclusive = False
    has_not_checked = False
    
    for dim_result in dimensions:
        if dim_result.dimension in REQUIRED_DIMENSIONS:
            if dim_result.status == DimensionStatus.FAIL:
                has_fail = True
            elif dim_result.status == DimensionStatus.INCONCLUSIVE:
                has_inconclusive = True
                cannot_prove.append(dim_result.dimension.value)
            elif dim_result.status == DimensionStatus.NOT_CHECKED:
                has_not_checked = True
                cannot_prove.append(dim_result.dimension.value)
    
    if has_fail:
        overall_status = "INVALID"
    elif has_inconclusive:
        overall_status = "INCONCLUSIVE"
    elif has_not_checked:
        overall_status = "INCONCLUSIVE"
    else:
        overall_status = "VALID"
    
    return CertificateVerification(
        certificate_id=cert.certificate_id,
        overall_status=overall_status,
        dimensions=dimensions,
        cannot_prove=cannot_prove,
        certificate_version=cert.version,
        verifier_version="0.1.0-slice1",
        verified_at=datetime.now(timezone.utc).isoformat(),
        details=""
    )


class VerificationStatus(str, Enum):
    VALID = "VALID"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    TAMPERED_EVIDENCE = "TAMPERED_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"
    MISSING_REFERENCE = "MISSING_REFERENCE"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"


@dataclass
class VerificationResult:
    status: VerificationStatus
    details: str = ""
    certificate_id: Optional[str] = None


def verify_certificate_simple(cert: Certificate, evidence: Optional[EvidencePackage], signer_public_key_bytes: bytes) -> VerificationResult:
    trust_store = TrustStore()
    trust_store.add_signer(TrustedSigner(
        signer_id=cert.signer_id,
        public_key=signer_public_key_bytes,
        name=cert.signer_id
    ))
    
    context = VerificationContext(trust_store=trust_store)
    result = verify_certificate(cert, evidence, context)
    
    status_map = {
        "VALID": VerificationStatus.VALID,
        "INVALID": VerificationStatus.INVALID_SIGNATURE,
        "INCONCLUSIVE": VerificationStatus.INCONCLUSIVE,
    }
    
    return VerificationResult(
        status=status_map.get(result.overall_status, VerificationStatus.INCONCLUSIVE),
        details="; ".join([f"{d.dimension.value}: {d.status.value} - {d.detail}" for d in result.dimensions]),
        certificate_id=cert.certificate_id
    )


def verify_evidence_only(cert: Certificate, evidence: Optional[EvidencePackage]) -> VerificationResult:
    context = VerificationContext(require_signer_trust=False, allow_unsigned=True)
    result = verify_certificate(cert, evidence, context)
    
    status_map = {
        "VALID": VerificationStatus.VALID,
        "INVALID": VerificationStatus.TAMPERED_EVIDENCE,
        "INCONCLUSIVE": VerificationStatus.INCONCLUSIVE,
    }
    
    return VerificationResult(
        status=status_map.get(result.overall_status, VerificationStatus.INCONCLUSIVE),
        details="; ".join([f"{d.dimension.value}: {d.status.value} - {d.detail}" for d in result.dimensions]),
        certificate_id=cert.certificate_id
    )
