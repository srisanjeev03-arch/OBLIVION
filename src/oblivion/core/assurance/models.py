"""Typed models for Assurance Assessment."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


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
    context: dict[str, Any] = field(default_factory=dict)


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
    recovered_hash: str | None = None
    explanation: str | None = None


@dataclass
class AssuranceResult:
    operation_id: str
    target_id: str
    timestamp: datetime
    status: AssuranceStatus
    confidence: AssuranceConfidence
    summary: str
    warnings: list[Warning] = field(default_factory=list)
    inconclusive_reasons: list[InconclusiveReason] = field(default_factory=list)
    residual_findings: list[ResidualFinding] = field(default_factory=list)
    recovery_test_results: list[RecoveryTestResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
