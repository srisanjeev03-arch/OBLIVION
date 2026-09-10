"""Certificate package: keys, issuance, trust, and independent verification.

The pieces fit together in one direction only:

    EvidenceRecord -> CertificateIssuer -> Certificate -> verify_certificate

and verification takes its facts from a :class:`VerificationContext` supplied by
the caller, never from the certificate under test.
"""

from .integrity import hash_integrity
from .issuer import (
    DEFAULT_SIGNER_ID,
    CertificateIssuanceError,
    CertificateIssuer,
    IssuanceRequest,
)
from .keys import (
    ENV_SIGNING_KEY,
    ENV_SIGNING_KEY_FILE,
    SigningIdentity,
    SigningKeyError,
    SigningKeyManager,
    derive_key_id,
    generate_private_key_hex,
)
from .models import (
    CERTIFICATE_VERSION,
    SUPPORTED_CERTIFICATE_VERSIONS,
    Certificate,
    new_certificate_id,
)
from .signer import Ed25519SignerVerifier
from .trust_model import (
    ENV_TRUSTED_SIGNERS,
    NullTrustStore,
    StaticTrustStore,
    TrustedKey,
    TrustStore,
    TrustStoreError,
    load_trust_store_from_env,
)
from .verification import REQUIRED_DIMENSIONS, VerificationContext, verify_certificate
from .verification_model import (
    VERIFIER_VERSION,
    CertificateVerificationResult,
    CheckResult,
    DimensionResult,
    VerificationDimension,
    VerificationResult,
    VerificationStatus,
)

__all__ = [
    "CERTIFICATE_VERSION",
    "DEFAULT_SIGNER_ID",
    "ENV_SIGNING_KEY",
    "ENV_SIGNING_KEY_FILE",
    "ENV_TRUSTED_SIGNERS",
    "REQUIRED_DIMENSIONS",
    "SUPPORTED_CERTIFICATE_VERSIONS",
    "VERIFIER_VERSION",
    "Certificate",
    "CertificateIssuanceError",
    "CertificateIssuer",
    "CertificateVerificationResult",
    "CheckResult",
    "DimensionResult",
    "Ed25519SignerVerifier",
    "IssuanceRequest",
    "NullTrustStore",
    "SigningIdentity",
    "SigningKeyError",
    "SigningKeyManager",
    "StaticTrustStore",
    "TrustStore",
    "TrustStoreError",
    "TrustedKey",
    "VerificationContext",
    "VerificationDimension",
    "VerificationResult",
    "VerificationStatus",
    "derive_key_id",
    "generate_private_key_hex",
    "hash_integrity",
    "load_trust_store_from_env",
    "new_certificate_id",
    "verify_certificate",
]
