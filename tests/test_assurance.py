"""Assurance rule behaviour.

The property under test throughout is that assurance never converts an absence
of evidence into a positive claim. Several tests here previously asserted the
opposite - notably that empty inputs yield PASSED/HIGH - because the rule was
written to read findings without asking whether any analysis had run. Those
expectations encoded the defect and are inverted below; the assertions that
described genuinely correct behaviour are unchanged.
"""

import pytest

from oblivion.core.assurance.engine import AssuranceEngine
from oblivion.core.assurance.models import (
    RECOVERY_DATA_NOT_RECOVERED,
    RECOVERY_DATA_WAS_RECOVERED,
    RECOVERY_TEST_INCONCLUSIVE,
    AnalysisState,
    AssuranceConfidence,
    AssuranceStatus,
    EvidenceCoverage,
    RecoveryTestResult,
    ResidualFinding,
)
from oblivion.core.assurance.rules import DefaultAssuranceRule

#: Both required analyses ran. Anything less cannot support a positive verdict.
FULL_COVERAGE = EvidenceCoverage(
    residual_analysis=AnalysisState.PERFORMED,
    recovery_test=AnalysisState.PERFORMED,
)

#: A recovery test that ran and did not get the data back.
RECOVERY_FAILED_AS_EXPECTED = [
    RecoveryTestResult(test_id="rt1", status=RECOVERY_DATA_NOT_RECOVERED)
]


@pytest.fixture
def assurance_engine():
    return AssuranceEngine(rule=DefaultAssuranceRule())


# --------------------------------------------------------------------------
# 1-4: absence of evidence must never be positive
# --------------------------------------------------------------------------

def test_empty_evidence_cannot_produce_passed(assurance_engine):
    """No findings and no declared coverage is the "nothing ran" case."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=[],
    )
    assert result.status is AssuranceStatus.INCONCLUSIVE
    assert result.status is not AssuranceStatus.PASSED
    assert result.confidence is AssuranceConfidence.LOW
    assert result.inconclusive_reasons, "an inconclusive result must say why"


def test_empty_residual_input_cannot_produce_passed(assurance_engine):
    """Recovery testing alone is not enough: residual analysis is required too."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=RECOVERY_FAILED_AS_EXPECTED,
        coverage=EvidenceCoverage(
            residual_analysis=AnalysisState.NOT_PERFORMED,
            recovery_test=AnalysisState.PERFORMED,
        ),
    )
    assert result.status is AssuranceStatus.INCONCLUSIVE
    codes = {r.reason_code for r in result.inconclusive_reasons}
    assert "RESIDUAL_ANALYSIS_NOT_PERFORMED" in codes


def test_missing_recovery_test_cannot_produce_passed(assurance_engine):
    """Residual analysis alone is not enough: recovery verification is required."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=[],
        coverage=EvidenceCoverage(
            residual_analysis=AnalysisState.PERFORMED,
            recovery_test=AnalysisState.NOT_PERFORMED,
        ),
    )
    assert result.status is AssuranceStatus.INCONCLUSIVE
    codes = {r.reason_code for r in result.inconclusive_reasons}
    assert "RECOVERY_TEST_NOT_PERFORMED" in codes


def test_unavailable_analysis_is_inconclusive_not_passed(assurance_engine):
    """An analysis that could not run is reported as such, not as a clean result."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=RECOVERY_FAILED_AS_EXPECTED,
        coverage=EvidenceCoverage(
            residual_analysis=AnalysisState.UNAVAILABLE,
            recovery_test=AnalysisState.PERFORMED,
        ),
    )
    assert result.status is AssuranceStatus.INCONCLUSIVE
    assert result.confidence is AssuranceConfidence.LOW
    codes = {r.reason_code for r in result.inconclusive_reasons}
    assert "RESIDUAL_ANALYSIS_UNAVAILABLE" in codes


def test_declared_recovery_test_with_no_results_is_inconclusive(assurance_engine):
    """Coverage claims must be corroborated by actual results."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=[],
        coverage=FULL_COVERAGE,
    )
    assert result.status is AssuranceStatus.INCONCLUSIVE
    codes = {r.reason_code for r in result.inconclusive_reasons}
    assert "RECOVERY_TEST_NO_RESULTS" in codes


def test_inconclusive_recovery_test_is_inconclusive(assurance_engine):
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=[
            RecoveryTestResult(test_id="rt1", status=RECOVERY_TEST_INCONCLUSIVE)
        ],
        coverage=FULL_COVERAGE,
    )
    assert result.status is AssuranceStatus.INCONCLUSIVE


# --------------------------------------------------------------------------
# 5: complete evidence still reaches the intended positive result
# --------------------------------------------------------------------------

def test_complete_evidence_can_still_pass(assurance_engine):
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=RECOVERY_FAILED_AS_EXPECTED,
        coverage=FULL_COVERAGE,
    )
    assert result.status is AssuranceStatus.PASSED
    assert result.confidence is AssuranceConfidence.HIGH
    assert not result.inconclusive_reasons


def test_passed_summary_makes_no_irrecoverability_claim(assurance_engine):
    """PASSED must stay bounded by the supported scope (docs/OBLIVION_DOCUMENTATION.md §36)."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=RECOVERY_FAILED_AS_EXPECTED,
        coverage=FULL_COVERAGE,
    )
    summary = result.summary.lower()
    assert "supported test scope" in summary
    for forbidden in ("irrecoverable", "unrecoverable", "guaranteed", "100%"):
        assert forbidden not in summary


def test_coverage_is_recorded_on_the_result(assurance_engine):
    """The verdict carries the coverage it was based on, for later audit."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=RECOVERY_FAILED_AS_EXPECTED,
        coverage=FULL_COVERAGE,
    )
    assert result.metadata["evidence_coverage"] == {
        "residual_analysis": "PERFORMED",
        "recovery_test": "PERFORMED",
    }


# --------------------------------------------------------------------------
# Conclusive negatives - unchanged behaviour, and independent of coverage
# --------------------------------------------------------------------------

def test_successful_recovery_fails(assurance_engine):
    """Recovering the data is conclusive regardless of coverage completeness."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=[
            RecoveryTestResult(test_id="test1", status=RECOVERY_DATA_WAS_RECOVERED)
        ],
    )
    assert result.status is AssuranceStatus.FAILED
    assert result.confidence is AssuranceConfidence.HIGH
    assert "recoverable" in result.summary


def test_critical_residual_fails(assurance_engine):
    """A critical artifact is conclusive regardless of coverage completeness."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[
            ResidualFinding(
                artifact_path="file1",
                finding_type="meta",
                severity="CRITICAL",
                explanation="leak",
            )
        ],
        recovery_results=[],
    )
    assert result.status is AssuranceStatus.FAILED
    assert result.confidence is AssuranceConfidence.HIGH


def test_non_critical_residual_is_partial(assurance_engine):
    """PARTIAL still requires the search to have happened."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[
            ResidualFinding(
                artifact_path="file1",
                finding_type="meta",
                severity="INFO",
                explanation="minor leak",
            )
        ],
        recovery_results=RECOVERY_FAILED_AS_EXPECTED,
        coverage=FULL_COVERAGE,
    )
    assert result.status is AssuranceStatus.PARTIAL
    assert result.confidence is AssuranceConfidence.MEDIUM


def test_recovery_that_did_not_recover_is_not_a_failure(assurance_engine):
    """A recovery test that failed to recover is the desired erasure outcome."""
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=RECOVERY_FAILED_AS_EXPECTED,
        coverage=FULL_COVERAGE,
    )
    assert result.status is AssuranceStatus.PASSED
    assert result.confidence is AssuranceConfidence.HIGH


# --------------------------------------------------------------------------
# The rule's own default, exercised directly
# --------------------------------------------------------------------------

def test_rule_defaults_to_no_coverage():
    """Calling the rule without coverage must not be a way around the gate."""
    evaluation = DefaultAssuranceRule().evaluate([], [])
    assert evaluation.status is AssuranceStatus.INCONCLUSIVE
    assert evaluation.confidence is AssuranceConfidence.LOW


def test_incomplete_coverage_lists_every_shortfall():
    evaluation = DefaultAssuranceRule().evaluate([], [], EvidenceCoverage())
    codes = {r.reason_code for r in evaluation.inconclusive_reasons}
    assert codes == {
        "RESIDUAL_ANALYSIS_NOT_PERFORMED",
        "RECOVERY_TEST_NOT_PERFORMED",
    }
