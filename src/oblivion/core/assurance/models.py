"""Typed models for Assurance Assessment."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, ClassVar


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


#: A recovery test that *succeeded* means the data was recovered, which is a
#: negative result for erasure assurance. The three values are spelled out here
#: because the polarity reads backwards at a glance.
RECOVERY_DATA_WAS_RECOVERED = "SUCCESS"
RECOVERY_DATA_NOT_RECOVERED = "FAILURE"
RECOVERY_TEST_INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class RecoveryTestResult:
    test_id: str
    status: str  # RECOVERY_DATA_WAS_RECOVERED | RECOVERY_DATA_NOT_RECOVERED | RECOVERY_TEST_INCONCLUSIVE
    recovered_hash: str | None = None
    explanation: str | None = None


class AnalysisState(Enum):
    """Whether a required analysis ran at all - separate from what it found.

    Findings alone cannot answer this. An empty list of residual findings is
    produced both by "scanned the target and found nothing" and by "never
    scanned", and those two must not lead to the same assurance claim.
    """

    #: Never attempted.
    NOT_PERFORMED = auto()
    #: Attempted, but could not run here (unsupported medium, missing
    #: capability, platform limitation, execution error).
    UNAVAILABLE = auto()
    #: Ran, but could not reach a determination.
    INCONCLUSIVE = auto()
    #: Some of the units of work this build supports ran; others did not.
    #:
    #: Added for audit finding M-2. Before it, "one of several methods ran" and
    #: "every method ran" were both reported as PERFORMED, which let a reader
    #: overestimate forensic coverage. PARTIAL says plainly that the search was
    #: real but incomplete - which is neither a clean result nor an absent one.
    PARTIAL = auto()
    #: Every unit of work this build supports ran and produced a determination
    #: that can be relied upon. Complete coverage *of what is supported* - the
    #: capabilities this build does not have are reported as limitations, never
    #: folded into this state.
    PERFORMED = auto()


@dataclass(frozen=True)
class EvidenceCoverage:
    """Declares which required analyses actually ran for an operation.

    Every field defaults to :attr:`AnalysisState.NOT_PERFORMED` so a caller that
    supplies nothing is treated as having proved nothing. That default is the
    fail-closed position and is deliberate: assurance must never reach a
    positive verdict merely because a caller omitted a description of its
    evidence.
    """

    residual_analysis: AnalysisState = AnalysisState.NOT_PERFORMED
    recovery_test: AnalysisState = AnalysisState.NOT_PERFORMED

    #: Analyses that must be PERFORMED before any positive assurance is possible.
    REQUIRED: ClassVar[tuple[str, ...]] = ("residual_analysis", "recovery_test")

    def shortfalls(self) -> list[tuple[str, "AnalysisState"]]:
        """Required analyses that did not reach ``PERFORMED``, in declared order."""
        return [
            (name, getattr(self, name))
            for name in self.REQUIRED
            if getattr(self, name) is not AnalysisState.PERFORMED
        ]

    def blocking_shortfalls(self) -> list[tuple[str, "AnalysisState"]]:
        """Shortfalls that prevent any positive verdict at all.

        A required analysis that never ran, could not run, or reached no
        determination leaves nothing to reason from. These are distinct from
        :meth:`partial_shortfalls`, where a real search happened but did not
        cover everything - that supports a qualified verdict, not no verdict.
        """
        blocking = {
            AnalysisState.NOT_PERFORMED,
            AnalysisState.UNAVAILABLE,
            AnalysisState.INCONCLUSIVE,
        }
        return [(n, s) for n, s in self.shortfalls() if s in blocking]

    def partial_shortfalls(self) -> list[tuple[str, "AnalysisState"]]:
        """Required analyses that ran, but did not cover everything supported."""
        return [(n, s) for n, s in self.shortfalls() if s is AnalysisState.PARTIAL]

    def is_complete(self) -> bool:
        """True only when every required analysis ran to full supported coverage."""
        return not self.shortfalls()


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
