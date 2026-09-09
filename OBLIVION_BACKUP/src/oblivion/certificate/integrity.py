"""Integrity hashing for Evidence Packages.

Provides deterministic hashing used to detect tampering of evidence
between signing and verification.
"""
from oblivion.core.evidence.canonicalize import canonical_hash
from oblivion.core.evidence.models import EvidencePackage


def hash_integrity(evidence: EvidencePackage) -> str:
    """Computes the SHA-256 hash of the canonicalized evidence package.

    Args:
        evidence: The evidence package to hash.

    Returns:
        Lowercase hex-encoded SHA-256 digest of the canonical JSON form.
    """
    return canonical_hash(evidence.to_dict())


__all__ = ["hash_integrity"]
