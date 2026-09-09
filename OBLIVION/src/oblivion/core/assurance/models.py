"""Typed models for Assurance Assessment."""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, Optional, List
from datetime import datetime


class AssuranceStatus(Enum):
    PASSED = auto()
    FAILED = auto()
    PARTIAL = auto()
    INCONCLUSIVE = auto()


class AssuranceConfidence(Enum):
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()


@dataclass
class Warning:
    code: str
    message: str
    severity: str = "WARNING"  # e.g., "INFO", "WARNING", "CRITICAL"


@dataclass
class InconclusiveReason:
    reason_code: str
    description: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResidualFinding:
    artifact_path: str
    finding_type: str
    severity: str
    explanation: str


@dataclass
class RecoveryTestResult:
    test_id: str
    status: str  # e.g., "SUCCESS", "FAILURE", "INCONCLUSIVE"
    recovered_hash: Optional[str] = None
    explanation: Optional[str] = None


@dataclass
class AssuranceResult:
    operation_id: str
    target_id: str
    timestamp: datetime
    status: AssuranceStatus
    confidence: AssuranceConfidence
    summary: str
    warnings: List[Warning] = field(default_factory=list)
    inconclusive_reasons: List[InconclusiveReason] = field(default_factory=list)
    residual_findings: List[ResidualFinding] = field(default_factory=list)
    recovery_test_results: List[RecoveryTestResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
