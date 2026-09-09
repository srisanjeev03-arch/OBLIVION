from typing import Any

from .models import EvidenceConfidence, EvidenceType, ResidualEvidence


class EvidenceComparator:
    @staticmethod
    def compare(baseline: dict[str, Any], actual_state: dict[str, Any]) -> list[ResidualEvidence]:
        """Compares baseline artifact with actual state and produces evidence."""
        evidence = []

        # Compare hashes
        baseline_hash = baseline.get("hashes", {}).get("sha256")
        actual_hash = actual_state.get("sha256")

        if baseline_hash and actual_hash:
            if baseline_hash == actual_hash:
                evidence.append(ResidualEvidence(
                    evidence_type=EvidenceType.HASH_MATCH,
                    confidence=EvidenceConfidence.HIGH,
                    explanation="SHA-256 hash matches.",
                    artifact_path=baseline["path"],
                    metadata={"original": baseline_hash, "actual": actual_hash}
                ))
            else:
                evidence.append(ResidualEvidence(
                    evidence_type=EvidenceType.HASH_MISMATCH,
                    confidence=EvidenceConfidence.HIGH,
                    explanation="SHA-256 hash mismatch.",
                    artifact_path=baseline["path"],
                    metadata={"original": baseline_hash, "actual": actual_hash}
                ))

        return evidence
