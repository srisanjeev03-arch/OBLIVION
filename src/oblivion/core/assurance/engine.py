"""Assurance Engine for evaluating evidence."""
import logging
from datetime import UTC, datetime
from typing import Any

from .models import (
    AssuranceResult,
    EvidenceCoverage,
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
        coverage: EvidenceCoverage | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AssuranceResult:
        """Assess assurance from the collected evidence.

        ``coverage`` states which required analyses actually ran. Omitting it
        means nothing is known to have run, and the assessment is inconclusive
        by construction - findings alone can never establish that a search took
        place. The resolved coverage is recorded in ``metadata`` so the reason
        for the verdict stays attached to the result.
        """
        resolved_coverage = coverage if coverage is not None else EvidenceCoverage()
        evaluation = self.rule.evaluate(residual_findings, recovery_results, resolved_coverage)

        result_metadata = dict(metadata or {})
        result_metadata["evidence_coverage"] = {
            name: getattr(resolved_coverage, name).name
            for name in EvidenceCoverage.REQUIRED
        }

        return AssuranceResult(
            operation_id=operation_id,
            target_id=target_id,
            timestamp=datetime.now(UTC),
            status=evaluation.status,
            confidence=evaluation.confidence,
            summary=evaluation.summary,
            inconclusive_reasons=evaluation.inconclusive_reasons,
            residual_findings=residual_findings,
            recovery_test_results=recovery_results,
            metadata=result_metadata,
        )
