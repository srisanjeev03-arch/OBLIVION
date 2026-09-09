import pytest

from oblivion.core.assurance.engine import AssuranceEngine
from oblivion.core.assurance.models import (
    AssuranceConfidence,
    AssuranceStatus,
    RecoveryTestResult,
    ResidualFinding,
)
from oblivion.core.assurance.rules import DefaultAssuranceRule


@pytest.fixture
def assurance_engine():
    return AssuranceEngine(rule=DefaultAssuranceRule())

def test_empty_evidence_passes(assurance_engine):
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=[],
    )
    assert result.status == AssuranceStatus.PASSED
    assert result.confidence == AssuranceConfidence.HIGH

def test_successful_recovery_fails(assurance_engine):
    recovery_results = [
        RecoveryTestResult(test_id="test1", status="SUCCESS")
    ]
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=recovery_results,
    )
    assert result.status == AssuranceStatus.FAILED
    assert result.confidence == AssuranceConfidence.HIGH
    assert "recoverable" in result.summary

def test_critical_residual_fails(assurance_engine):
    residual_findings = [
        ResidualFinding(artifact_path="file1", finding_type="meta", severity="CRITICAL", explanation="leak")
    ]
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=residual_findings,
        recovery_results=[],
    )
    assert result.status == AssuranceStatus.FAILED
    assert result.confidence == AssuranceConfidence.HIGH

def test_non_critical_residual_is_partial(assurance_engine):
    residual_findings = [
        ResidualFinding(artifact_path="file1", finding_type="meta", severity="INFO", explanation="minor leak")
    ]
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=residual_findings,
        recovery_results=[],
    )
    assert result.status == AssuranceStatus.PARTIAL
    assert result.confidence == AssuranceConfidence.MEDIUM

def test_failed_recovery_test_should_not_cause_failure(assurance_engine):
    recovery_results = [
        RecoveryTestResult(test_id="test1", status="FAILURE")
    ]
    result = assurance_engine.assess(
        operation_id="op1",
        target_id="target1",
        residual_findings=[],
        recovery_results=recovery_results,
    )
    assert result.status == AssuranceStatus.PASSED
    assert result.confidence == AssuranceConfidence.HIGH
