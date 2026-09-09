from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Any, List, Optional
from pathlib import Path

class RecoveryMode(Enum):
    FILESYSTEM_AWARE = auto()
    METADATA_INSPECTION = auto()

class RecoveryConfidence(Enum):
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()
    INCONCLUSIVE = auto()

class RecoveryResult(Enum):
    RECOVERED = auto()
    NOT_DETECTED = auto()
    PARTIAL = auto()
    FAILED = auto()
    INCONCLUSIVE = auto()

@dataclass
class RecoveryCandidate:
    item_id: str
    original_name: Optional[str]
    size: int
    source_evidence: str
    metadata: Dict[str, Any]

@dataclass
class RecoveryItem:
    item_id: str
    original_name: Optional[str]
    size: int
    relationship: str
    source_evidence: str
    destination: Path
    hash: Optional[str]
    confidence: RecoveryConfidence
    result: RecoveryResult
    metadata: Dict[str, Any]

class RecoveryAdapter(ABC):
    @abstractmethod
    def scan(self, source_path: Path, mode: RecoveryMode) -> List[RecoveryItem]:
        """Performs a read-only scan of the source path."""
        pass
