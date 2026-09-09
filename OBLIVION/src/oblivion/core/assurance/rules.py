"""Deterministic rules for Assurance Assessment."""
from typing import List, Tuple
from .models import (
    AssuranceStatus,
    AssuranceConfidence,
    ResidualFinding,
    RecoveryTestResult,
)

class AssuranceRule:
    """Base class for assurance evaluation rules."""
    def evaluate(self, residual_findings: List[ResidualFinding], recovery_results: List[RecoveryTestResult]) -> Tuple[AssuranceStatus, AssuranceConfidence, str]:
        raise NotImplementedError

class DefaultAssuranceRule(AssuranceRule):
    """
    Default rules for assurance evaluation.
    - Fails if recovery is possible.
    - Partial if residuals exist.
    - Passed otherwise.
    """
    def evaluate(self, residual_findings: List[ResidualFinding], recovery_results: List[RecoveryTestResult]) -> Tuple[AssuranceStatus, AssuranceConfidence, str]:
        # 1. Check recovery tests (Highest priority failure)
        for result in recovery_results:
            if result.status == "SUCCESS":
                return (AssuranceStatus.FAILED, AssuranceConfidence.HIGH, f"Recovery test {result.test_id} succeeded: Data recoverable.")

        # 2. Check residual findings
        if residual_findings:
            # Analyze findings for severity
            critical_findings = [f for f in residual_findings if f.severity == "CRITICAL"]
            if critical_findings:
                return (AssuranceStatus.FAILED, AssuranceConfidence.HIGH, "Critical residual artifacts found.")
            return (AssuranceStatus.PARTIAL, AssuranceConfidence.MEDIUM, "Residual artifacts found, but none critical.")

        # 3. Passed
        return (AssuranceStatus.PASSED, AssuranceConfidence.HIGH, "All tests passed and no residuals found.")
