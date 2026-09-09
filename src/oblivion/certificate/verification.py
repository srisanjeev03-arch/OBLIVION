"""Fail-closed, multi-dimensional certificate verification."""
import binascii
import hmac
import re
from datetime import datetime

from oblivion.core.evidence.models import EvidencePackage

from .integrity import hash_integrity
from .models import Certificate
from .signer import Ed25519SignerVerifier
from .trust_model import NullTrustStore, TrustStore
from .verification_model import (
    CertificateVerificationResult,
    CheckResult,
    DimensionResult,
    VerificationDimension,
    VerificationResult,
    VerificationStatus,
)

SUPPORTED_CERTIFICATE_VERSIONS: set[str] = {"1.0.0"}
REQUIRED_DIMENSIONS_FOR_VALID = set(VerificationDimension)


def _key(value: str | bytes | None) -> bytes | None:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        try:
            return binascii.unhexlify(value)
        except (binascii.Error, ValueError):
            return None
    return None


def verify_certificate(cert: Certificate, evidence: EvidencePackage | None, signer_public_key: bytes, trust_store: TrustStore | None = None, chain_result: CheckResult | None = None) -> CertificateVerificationResult:
    """Verify every certificate dimension without turning assertions into proof."""
    trust_store = trust_store or NullTrustStore()
    results: list[DimensionResult] = []
    errors: list[str] = []
    if not isinstance(cert.certificate_id, str) or not cert.certificate_id:
        errors.append("missing certificate_id")
    if not isinstance(cert.evidence_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", cert.evidence_hash):
        errors.append("invalid evidence_hash")
    if not isinstance(cert.signature, str):
        errors.append("missing signature")
    else:
        try:
            if len(binascii.unhexlify(cert.signature)) != 64:
                errors.append("signature is not 64 bytes")
        except (binascii.Error, ValueError):
            errors.append("signature is not hexadecimal")
    if not isinstance(cert.signer_id, str) or not cert.signer_id:
        errors.append("missing signer_id")
    if not isinstance(cert.timestamp, datetime):
        errors.append("invalid timestamp")
    results.append(DimensionResult(VerificationDimension.STRUCTURE, CheckResult.FAIL if errors else CheckResult.PASS, "; ".join(errors) if errors else "Certificate structure is valid."))
    supported = cert.version in SUPPORTED_CERTIFICATE_VERSIONS
    results.append(DimensionResult(VerificationDimension.VERSION_COMPATIBILITY, CheckResult.PASS if supported else CheckResult.FAIL, f"Version {cert.version} is supported." if supported else f"Version {cert.version} is not supported."))

    evidence_digest_match = False
    if evidence is None:
        results.extend([
            DimensionResult(VerificationDimension.EVIDENCE_AVAILABILITY, CheckResult.FAIL, "Evidence package is missing."),
            DimensionResult(VerificationDimension.EVIDENCE_DIGEST, CheckResult.NOT_CHECKED, "Evidence digest cannot be computed without evidence."),
        ])
    else:
        results.append(DimensionResult(VerificationDimension.EVIDENCE_AVAILABILITY, CheckResult.PASS, "Evidence package is available."))
        try:
            evidence_digest_match = hmac.compare_digest(hash_integrity(evidence).lower(), cert.evidence_hash.lower())
            results.append(DimensionResult(VerificationDimension.EVIDENCE_DIGEST, CheckResult.PASS if evidence_digest_match else CheckResult.FAIL, "Evidence digest matches canonical SHA-256." if evidence_digest_match else "Evidence digest does not match the certificate."))
        except (TypeError, ValueError):
            results.append(DimensionResult(VerificationDimension.EVIDENCE_DIGEST, CheckResult.INCONCLUSIVE, "Evidence cannot be canonically hashed."))

    embedded_key = _key(cert.public_key)
    if embedded_key is None:
        results.append(DimensionResult(VerificationDimension.PUBLIC_KEY_CONSISTENCY, CheckResult.NOT_CHECKED, "Certificate has no decodable public-key binding."))
    elif len(embedded_key) != 32 or not isinstance(signer_public_key, bytes) or len(signer_public_key) != 32:
        results.append(DimensionResult(VerificationDimension.PUBLIC_KEY_CONSISTENCY, CheckResult.FAIL, "Certificate or verification key is not a 32-byte Ed25519 key."))
    elif hmac.compare_digest(embedded_key, signer_public_key):
        results.append(DimensionResult(VerificationDimension.PUBLIC_KEY_CONSISTENCY, CheckResult.PASS, "Certificate public key matches the independently supplied key."))
    else:
        results.append(DimensionResult(VerificationDimension.PUBLIC_KEY_CONSISTENCY, CheckResult.FAIL, "Certificate public key differs from the verification key."))

    signature_valid = False
    if not isinstance(signer_public_key, bytes) or len(signer_public_key) != 32:
        results.append(DimensionResult(VerificationDimension.SIGNATURE_VALIDITY, CheckResult.FAIL, "A 32-byte Ed25519 verification key is required."))
    else:
        try:
            signature_valid = Ed25519SignerVerifier.verify(signer_public_key, cert.evidence_hash.encode("ascii"), binascii.unhexlify(cert.signature))
            results.append(DimensionResult(VerificationDimension.SIGNATURE_VALIDITY, CheckResult.PASS if signature_valid else CheckResult.FAIL, "Ed25519 signature is valid." if signature_valid else "Ed25519 signature verification failed."))
        except (AttributeError, UnicodeEncodeError, binascii.Error, ValueError, TypeError):
            results.append(DimensionResult(VerificationDimension.SIGNATURE_VALIDITY, CheckResult.FAIL, "Signature encoding is invalid."))

    try:
        trust = trust_store.is_trusted(cert.signer_id, signer_public_key, cert.timestamp)
    except (OSError, RuntimeError, TypeError, ValueError):
        trust = CheckResult.INCONCLUSIVE
    signer_trusted = trust is CheckResult.PASS
    trust_detail = {
        CheckResult.PASS: "Signer key is trusted by the configured TrustStore.",
        CheckResult.FAIL: "Signer key is untrusted, revoked, expired, or mismatched.",
        CheckResult.NOT_CHECKED: "No configured trusted key establishes signer trust.",
        CheckResult.INCONCLUSIVE: "Signer trust could not be determined.",
    }[trust]
    results.append(DimensionResult(VerificationDimension.SIGNER_TRUST, trust, trust_detail))
    # Evidence self-assertions do not prove ledger integrity. Phase 25 supplies
    # the independently derived result through this explicit input.
    chain_status = chain_result or CheckResult.NOT_CHECKED
    chain_detail = {
        CheckResult.PASS: "An independent event-chain verifier reported integrity intact.",
        CheckResult.FAIL: "An independent event-chain verifier reported an integrity failure.",
        CheckResult.NOT_CHECKED: "No independently verified event-chain result was supplied.",
        CheckResult.INCONCLUSIVE: "The independent event-chain verifier was inconclusive.",
    }[chain_status]
    results.append(DimensionResult(VerificationDimension.EVIDENCE_CHAIN_INTEGRITY, chain_status, chain_detail))

    if evidence is None:
        results.extend([
            DimensionResult(VerificationDimension.OPERATION_CONSISTENCY, CheckResult.NOT_CHECKED, "Operation binding cannot be checked without evidence."),
            DimensionResult(VerificationDimension.TARGET_CONSISTENCY, CheckResult.NOT_CHECKED, "Target binding cannot be checked without evidence."),
        ])
    else:
        if cert.operation_id:
            operation_result = CheckResult.PASS if cert.operation_id == evidence.operation_id else CheckResult.FAIL
            operation_detail = "Certificate operation identifier matches evidence." if operation_result is CheckResult.PASS else "Certificate operation identifier differs from evidence."
        elif cert.evidence_id == evidence.operation_id:
            operation_result, operation_detail = CheckResult.PASS, "Legacy evidence identifier matches the evidence operation identifier."
        else:
            operation_result, operation_detail = CheckResult.NOT_CHECKED, "Certificate lacks an operation identifier binding."
        results.append(DimensionResult(VerificationDimension.OPERATION_CONSISTENCY, operation_result, operation_detail))
        target_valid = bool(evidence.target_identity) and isinstance(evidence.target_hash, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", evidence.target_hash))
        results.append(DimensionResult(VerificationDimension.TARGET_CONSISTENCY, CheckResult.PASS if target_valid else CheckResult.FAIL, "Evidence contains a target identity and syntactically valid baseline digest." if target_valid else "Evidence target identity or baseline digest is malformed."))

    if any(item.result is CheckResult.FAIL for item in results):
        overall = VerificationStatus.INVALID.value
    elif any(item.result in (CheckResult.NOT_CHECKED, CheckResult.INCONCLUSIVE) for item in results):
        overall = VerificationStatus.INCONCLUSIVE.value
    else:
        overall = VerificationStatus.VALID.value
    return CertificateVerificationResult(cert.certificate_id, overall, results, signature_valid, evidence_digest_match, signer_trusted, [item.dimension.value for item in results if item.result in (CheckResult.NOT_CHECKED, CheckResult.INCONCLUSIVE)])


def verify_evidence_only(evidence: EvidencePackage, signer_public_key: bytes, signature_hex: str) -> VerificationResult:
    """Legacy raw-evidence signature helper; it makes no certificate claim."""
    try:
        valid = Ed25519SignerVerifier.verify(signer_public_key, hash_integrity(evidence).encode("ascii"), binascii.unhexlify(signature_hex))
    except (binascii.Error, ValueError, TypeError):
        valid = False
    return VerificationResult(valid, "VALID" if valid else "INVALID", True, valid, "Raw evidence signature check only.")


__all__ = ["REQUIRED_DIMENSIONS_FOR_VALID", "SUPPORTED_CERTIFICATE_VERSIONS", "verify_certificate", "verify_evidence_only"]
