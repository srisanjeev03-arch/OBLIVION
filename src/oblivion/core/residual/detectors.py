from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import EvidenceConfidence, EvidenceType, ResidualEvidence


class ResidualDetector(ABC):
    @abstractmethod
    def detect(self, baseline: dict[str, Any], current_path: Path) -> list[ResidualEvidence]:
        """Scans for remnants based on baseline information."""

class FileSystemResidualDetector(ResidualDetector):
    def detect(self, baseline: dict[str, Any], current_path: Path) -> list[ResidualEvidence]:
        evidence = []
        if current_path.exists():
            evidence.append(ResidualEvidence(
                evidence_type=EvidenceType.FILE_PRESENT if current_path.is_file() else EvidenceType.DIRECTORY_REMAINS,
                confidence=EvidenceConfidence.HIGH,
                explanation=f"Target {current_path} still exists.",
                artifact_path=str(current_path),
                metadata={}
            ))
        else:
            evidence.append(ResidualEvidence(
                evidence_type=EvidenceType.FILE_ABSENT,
                confidence=EvidenceConfidence.HIGH,
                explanation=f"Target {current_path} is absent.",
                artifact_path=str(current_path),
                metadata={}
            ))
        return evidence
