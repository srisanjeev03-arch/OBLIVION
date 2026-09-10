"""Certificate package: models, signing, integrity, trust store, and multi-dimensional verification."""
from .integrity import hash_integrity
from .keys import (
    ENV_SIGNING_KEY,
    ENV_SIGNING_KEY_FILE,
    SigningIdentity,
    SigningKeyError,
    SigningKeyManager,
    derive_key_id,
    generate_private_key_hex,
)
from .models import Certificate
from .signer import Ed25519SignerVerifier
from .trust_model import NullTrustStore, StaticTrustStore, TrustedKey, TrustStore
from .verification import (
    REQUIRED_DIMENSIONS_FOR_VALID,
    SUPPORTED_CERTIFICATE_VERSIONS,
    verify_certificate,
    verify_evidence_only,
)
from .verification_model import (
    CertificateVerificationResult,
    CheckResult,
    DimensionResult,
    VerificationDimension,
    VerificationResult,
    VerificationStatus,
)

__all__ = [
    "ENV_SIGNING_KEY",
    "ENV_SIGNING_KEY_FILE",
    "REQUIRED_DIMENSIONS_FOR_VALID",
    "SigningIdentity",
    "SigningKeyError",
    "SigningKeyManager",
    "derive_key_id",
    "generate_private_key_hex",
    "SUPPORTED_CERTIFICATE_VERSIONS",
    "Certificate",
    "CertificateVerificationResult",
    "CheckResult",
    "DimensionResult",
    "Ed25519SignerVerifier",
    "NullTrustStore",
    "StaticTrustStore",
    "TrustStore",
    "TrustedKey",
    "VerificationDimension",
    "VerificationResult",
    "VerificationStatus",
    "hash_integrity",
    "verify_certificate",
    "verify_evidence_only",
]
