"""Typed models for certificates used by the verifier."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Certificate:
    certificate_id: str
    evidence_id: str
    evidence_hash: str  # The SHA-256 hash of the canonicalized evidence package
    signature: str      # Ed25519 signature of evidence_hash
    signer_id: str
    timestamp: datetime
    version: str = "1.0.0"
    # Optional only for legacy persisted certificates.  Missing bindings are
    # reported as INCONCLUSIVE rather than being silently accepted.
    operation_id: str | None = None
    public_key: str | bytes | None = None
