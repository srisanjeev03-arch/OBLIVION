"""Assurance Engine for evaluating evidence."""
import logging
from datetime import datetime
from typing import Any

from .models import (
    AssuranceResult,
    RecoveryTestResult,
    ResidualFinding,
)
from .rules import AssuranceRule, DefaultAssuranceRule

logger = logging.getLogger(__name__)

class AssuranceEngine:
    """
    AssuranceEngine orchestrates evidence evaluation to determine the assurance status of an operation.
    """

    def __init__(self, rule: AssuranceRule | None = None):
        self.rule = rule or DefaultAssuranceRule()

    def assess(
        self,
        operation_id: str,
        target_id: str,
        residual_findings: list[ResidualFinding],
        recovery_results: list[RecoveryTestResult],
        metadata: dict[str, Any] | None = None,
    ) -> AssuranceResult:
        """
        Assesses assurance based on collected evidence.
        """
        status, confidence, summary = self.rule.evaluate(residual_findings, recovery_results)

        return AssuranceResult(
            operation_id=operation_id,
            target_id=target_id,
            timestamp=datetime.now(),
            status=status,
            confidence=confidence,
            summary=summary,
            residual_findings=residual_findings,
            recovery_test_results=recovery_results,
            metadata=metadata or {},
        )
