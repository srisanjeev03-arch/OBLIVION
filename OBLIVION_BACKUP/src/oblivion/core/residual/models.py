"""Typed models for Residual Analysis."""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, Optional, List


class ResidualStatus(Enum):
    NO_RESIDUAL_DETECTED = auto()
    RESIDUAL_DETECTED = auto()
    PARTIAL_RESIDUAL = auto()
    INCONCLUSIVE = auto()


class EvidenceType(Enum):
    FILE_PRESENT = auto()
    FILE_ABSENT = auto()
    HASH_MATCH = auto()
    HASH_MISMATCH = auto()
    METADATA_REMAINS = auto()
    DIRECTORY_REMAINS = auto()
    SIZE_MISMATCH = auto()
    TIMESTAMP_EVIDENCE = auto()
    RECOVERY_CANDIDATE = auto()
    UNREADABLE = auto()
    ANALYSIS_LIMITATION = auto()


class EvidenceConfidence(Enum):
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()
    INCONCLUSIVE = auto()


@dataclass
class ResidualEvidence:
    evidence_type: EvidenceType
    confidence: EvidenceConfidence
    explanation: str
    artifact_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResidualResult:
    operation_id: str
    status: ResidualStatus
    evidence: List[ResidualEvidence] = field(default_factory=list)
    summary: str = ""
    limitations: List[str] = field(default_factory=list)
    state: str = ""
