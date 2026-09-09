"""Evidence Engine for signing and verifying evidence packages."""
from typing import Dict, Any, Optional
from .models import EvidencePackage
from .canonicalize import canonicalize, canonical_hash
from oblivion.certificate.signer import Ed25519SignerVerifier

class EvidenceEngine:
    def __init__(self, signer: Ed25519SignerVerifier):
        self.signer = signer

    def generate_signed_evidence(self, evidence: EvidencePackage) -> Dict[str, Any]:
        """Sign an evidence package."""
        data = evidence.to_dict()
        data_hash = canonical_hash(data)
        canonical_bytes = canonicalize(data)
        signature = self.signer.sign(canonical_bytes)

        return {
            "evidence": data,
            "hash": data_hash,
            "signature": signature.hex(),
            "public_key": self.signer.get_public_key_bytes().hex()
        }

    @staticmethod
    def verify_evidence(evidence_data: Dict[str, Any], signature_hex: str, public_key_hex: str) -> bool:
        """Verify an evidence package."""
        canonical_bytes = canonicalize(evidence_data)
        signature = bytes.fromhex(signature_hex)
        public_key = bytes.fromhex(public_key_hex)

        return Ed25519SignerVerifier.verify(public_key, canonical_bytes, signature)
