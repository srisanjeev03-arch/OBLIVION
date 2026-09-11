"""Coverage semantics after audit finding M-2.

The finding was that one word meant two things. `PERFORMED` from the residual
sweep meant "every scanner ran"; `PERFORMED` from recovery testing meant "at
least one method was attempted". Both fed the same `EvidenceCoverage`, so a
reader could not tell a complete search from a single weak one.

These tests pin the repaired vocabulary:

* `PERFORMED` means every unit of work **this build supports** ran - identically
  for scanners and for recovery methods.
* `PARTIAL` means a real search happened but did not cover everything supported.
* `UNAVAILABLE` and `NOT_PERFORMED` mean nothing usable was produced.
* Capabilities this build does not have are *limitations*, never gaps folded
  into `PERFORMED`.

And the one that matters most: "one method attempted" must never survive
serialization looking like "all methods performed".
"""

from __future__ import annotations

import hashlib
import json

import pytest

from oblivion.core.assurance.engine import AssuranceEngine
from oblivion.core.assurance.models import (
    RECOVERY_DATA_NOT_RECOVERED,
    AnalysisState,
    AssuranceStatus,
    EvidenceCoverage,
    ResidualFinding,
)
from oblivion.core.evidence.canonicalize import canonicalize
from oblivion.core.recovery.testing import (
    UNAVAILABLE_METHODS,
    MethodOutcome,
    RecoveryMethod,
    RecoveryTester,
    RecoveryTestReport,
)
from oblivion.core.residual.models import (
    EvidenceConfidence,
    EvidenceType,
    ResidualEvidence,
)
from oblivion.core.residual.scanners import ResidualScanReport, ScanOutcome


def unavailable_outcomes() -> tuple[MethodOutcome, ...]:
    """The five methods this build can never perform."""
    return tuple(
        MethodOutcome(method, AnalysisState.UNAVAILABLE, None, reason)
        for method, reason in UNAVAILABLE_METHODS.items()
    )


def attempted(method: RecoveryMethod, *, recovered: bool) -> MethodOutcome:
    return MethodOutcome(
        method, AnalysisState.PERFORMED, recovered, f"{method.value} ran"
    )


# ---------------------------------------------------------------------------
# 1-6. Recovery coverage
# ---------------------------------------------------------------------------


def test_1_recovery_with_zero_attempted_methods_is_unavailable():
    """Only unperformable methods were offered, so nothing was established."""
    report = RecoveryTestReport(unavailable_outcomes())

    assert report.coverage is AnalysisState.UNAVAILABLE
    assert report.attempted == []
    assert report.method_coverage["supported"] == []
    assert report.method_coverage["attempted"] == []


def test_2_one_supported_method_of_several_is_partial():
    """The exact shape audit finding M-2 described.

    Two supported methods exist; one ran. Before the fix this reported
    PERFORMED, which is what let a reader overestimate coverage.
    """
    report = RecoveryTestReport(
        (
            attempted(RecoveryMethod.FILESYSTEM_ENUMERATION, recovered=False),
            MethodOutcome(
                RecoveryMethod.VAULT_ROUND_TRIP,
                AnalysisState.UNAVAILABLE,
                None,
                "no vault object was read back",
            ),
            *unavailable_outcomes(),
        )
    )

    assert report.coverage is AnalysisState.PARTIAL
    assert report.method_coverage["supported"] == [
        RecoveryMethod.FILESYSTEM_ENUMERATION.value,
        RecoveryMethod.VAULT_ROUND_TRIP.value,
    ]
    assert report.method_coverage["attempted"] == [
        RecoveryMethod.FILESYSTEM_ENUMERATION.value
    ]


def test_3_all_supported_methods_attempted_is_performed():
    """PERFORMED is complete coverage *of what this build supports*."""
    report = RecoveryTestReport(
        (
            attempted(RecoveryMethod.FILESYSTEM_ENUMERATION, recovered=False),
            attempted(RecoveryMethod.VAULT_ROUND_TRIP, recovered=True),
            *unavailable_outcomes(),
        )
    )

    assert report.coverage is AnalysisState.PERFORMED
    assert len(report.method_coverage["attempted"]) == 2
    # The five it cannot do are still named, not silently absorbed.
    assert len(report.method_coverage["unavailable"]) == len(UNAVAILABLE_METHODS)


def test_4_a_failed_method_is_recorded_as_failed_not_missing():
    """"Ran and did not recover" is a result, and a different one from "absent"."""
    report = RecoveryTestReport(
        (attempted(RecoveryMethod.FILESYSTEM_ENUMERATION, recovered=False),)
    )

    assert report.method_coverage["failed"] == [
        RecoveryMethod.FILESYSTEM_ENUMERATION.value
    ]
    assert report.method_coverage["successful"] == []
    assert report.data_was_recovered is False
    assert report.coverage is AnalysisState.PERFORMED


def test_5_an_unavailable_method_never_reports_a_result():
    """Enforced in the type: a method that did not run cannot assert anything."""
    with pytest.raises(ValueError, match="must assert nothing"):
        MethodOutcome(RecoveryMethod.MFT_RECORD, AnalysisState.UNAVAILABLE, False, "x")

    report = RecoveryTestReport(unavailable_outcomes())
    assert all(o.recovered is None for o in report.not_attempted)


def test_6_mixed_attempted_failed_and_unavailable_are_kept_apart():
    """Every method lands in exactly one bucket, and the buckets partition."""
    report = RecoveryTestReport(
        (
            attempted(RecoveryMethod.FILESYSTEM_ENUMERATION, recovered=True),
            attempted(RecoveryMethod.VAULT_ROUND_TRIP, recovered=False),
            *unavailable_outcomes(),
        )
    )
    coverage = report.method_coverage

    assert coverage["successful"] == [RecoveryMethod.FILESYSTEM_ENUMERATION.value]
    assert coverage["failed"] == [RecoveryMethod.VAULT_ROUND_TRIP.value]
    assert set(coverage["attempted"]) == set(
        coverage["successful"] + coverage["failed"]
    )
    assert not set(coverage["attempted"]) & set(coverage["unavailable"])
    assert report.data_was_recovered is True


# ---------------------------------------------------------------------------
# 7. Residual coverage
# ---------------------------------------------------------------------------


def test_7_incomplete_scanner_coverage_is_partial_not_performed():
    """One scanner that could not run makes the sweep incomplete."""
    report = ResidualScanReport(
        (
            ScanOutcome("path_existence", AnalysisState.PERFORMED),
            ScanOutcome("content_copy_by_hash", AnalysisState.PERFORMED),
            ScanOutcome(
                "alternate_data_streams",
                AnalysisState.UNAVAILABLE,
                limitation="not an NTFS host",
            ),
        )
    )

    assert report.coverage is AnalysisState.PARTIAL
    assert report.scanner_coverage["ran"] == [
        "path_existence",
        "content_copy_by_hash",
    ]
    assert report.scanner_coverage["unavailable"] == ["alternate_data_streams"]


def test_7b_every_scanner_running_is_performed():
    report = ResidualScanReport(
        (
            ScanOutcome("path_existence", AnalysisState.PERFORMED),
            ScanOutcome("content_copy_by_hash", AnalysisState.PERFORMED),
        )
    )
    assert report.coverage is AnalysisState.PERFORMED
    assert report.scanner_coverage["unavailable"] == []


def test_7c_no_scanner_running_is_unavailable():
    report = ResidualScanReport(
        (
            ScanOutcome("path_existence", AnalysisState.UNAVAILABLE),
            ScanOutcome("content_copy_by_hash", AnalysisState.UNAVAILABLE),
        )
    )
    assert report.coverage is AnalysisState.UNAVAILABLE


# ---------------------------------------------------------------------------
# 8-9. Assurance consumption
# ---------------------------------------------------------------------------


def assess(residual_state, recovery_state, *, findings=None, results=None):
    return AssuranceEngine().assess(
        operation_id="op-1",
        target_id="tgt-1",
        residual_findings=findings or [],
        recovery_results=results
        or [
            type(
                "R",
                (),
                {
                    "test_id": "filesystem_enumeration",
                    "status": RECOVERY_DATA_NOT_RECOVERED,
                    "recovered_hash": None,
                    "explanation": "ran",
                },
            )()
        ],
        coverage=EvidenceCoverage(
            residual_analysis=residual_state, recovery_test=recovery_state
        ),
    )


def test_8_partial_recovery_coverage_yields_partial_assurance():
    """Real evidence, incomplete search: neither PASSED nor INCONCLUSIVE.

    This is the semantic correction M-2 asked for. A partial search produced
    genuine evidence, so discarding it as inconclusive would be wrong - and
    calling it PASSED would overstate it.
    """
    result = assess(AnalysisState.PERFORMED, AnalysisState.PARTIAL)

    assert result.status is AssuranceStatus.PARTIAL
    assert "coverage was incomplete" in result.summary
    assert "recovery test" in result.summary


def test_8b_complete_coverage_still_yields_passed():
    """The fix must not lower results that were always properly earned."""
    result = assess(AnalysisState.PERFORMED, AnalysisState.PERFORMED)
    assert result.status is AssuranceStatus.PASSED


def test_9_unavailable_recovery_coverage_yields_inconclusive():
    """Nothing ran, so there is nothing to reason from."""
    result = assess(AnalysisState.PERFORMED, AnalysisState.UNAVAILABLE)

    assert result.status is AssuranceStatus.INCONCLUSIVE
    assert "required evidence is missing" in result.summary


def test_9b_not_performed_recovery_coverage_yields_inconclusive():
    result = assess(AnalysisState.PERFORMED, AnalysisState.NOT_PERFORMED)
    assert result.status is AssuranceStatus.INCONCLUSIVE


def test_9c_partial_residual_coverage_also_yields_partial():
    result = assess(AnalysisState.PARTIAL, AnalysisState.PERFORMED)

    assert result.status is AssuranceStatus.PARTIAL
    assert "residual analysis" in result.summary


def test_9d_a_recovered_target_still_fails_regardless_of_coverage():
    """Conclusive negatives do not depend on how complete the search was."""
    recovered = type(
        "R",
        (),
        {
            "test_id": "filesystem_enumeration",
            "status": "SUCCESS",
            "recovered_hash": None,
            "explanation": "recovered",
        },
    )()
    result = assess(AnalysisState.PARTIAL, AnalysisState.PARTIAL, results=[recovered])

    assert result.status is AssuranceStatus.FAILED


def test_9e_critical_residual_findings_still_fail_under_partial_coverage():
    finding = ResidualFinding(
        artifact_path="copy.txt",
        finding_type="HASH_MATCH",
        severity="CRITICAL",
        explanation="byte-identical copy survives",
    )
    result = assess(AnalysisState.PARTIAL, AnalysisState.PARTIAL, findings=[finding])

    assert result.status is AssuranceStatus.FAILED


# ---------------------------------------------------------------------------
# 10. Serialization must not launder partial coverage into complete coverage
# ---------------------------------------------------------------------------


def test_10_one_attempted_method_never_serializes_as_all_performed():
    """The headline guarantee of this remediation.

    A report where one of two supported methods ran must not, after
    serialization, be readable as a complete search.
    """
    report = RecoveryTestReport(
        (
            attempted(RecoveryMethod.FILESYSTEM_ENUMERATION, recovered=False),
            MethodOutcome(
                RecoveryMethod.VAULT_ROUND_TRIP,
                AnalysisState.UNAVAILABLE,
                None,
                "no vault object was read back",
            ),
            *unavailable_outcomes(),
        )
    )

    payload = report.to_dict()
    assert payload["coverage"] == AnalysisState.PARTIAL.name
    assert payload["coverage"] != AnalysisState.PERFORMED.name

    methods = payload["method_coverage"]
    assert len(methods["attempted"]) == 1
    assert len(methods["supported"]) == 2
    assert methods["attempted"] != methods["supported"]

    # And it survives a canonical round trip byte-for-byte.
    restored = json.loads(canonicalize(payload).decode("utf-8"))
    assert restored["coverage"] == AnalysisState.PARTIAL.name
    assert restored["method_coverage"]["attempted"] == methods["attempted"]
    assert restored["method_coverage"]["supported"] == methods["supported"]


def test_10b_the_unattempted_methods_survive_serialization(temp_dir):
    """A real run's report keeps naming what it did not do."""
    target = temp_dir / "gone.txt"
    baseline = {"hashes": {"sha256": hashlib.sha256(b"x").hexdigest()}}

    payload = RecoveryTester().run(baseline, target).to_dict()
    restored = json.loads(canonicalize(payload).decode("utf-8"))

    assert set(restored["method_coverage"]["unavailable"]) == {
        m.value for m in UNAVAILABLE_METHODS
    }
    assert "establishes that the data is" in restored["scope_note"]


def test_10c_residual_scanner_coverage_survives_serialization():
    report = ResidualScanReport(
        (
            ScanOutcome(
                "path_existence",
                AnalysisState.PERFORMED,
                (
                    ResidualEvidence(
                        evidence_type=EvidenceType.FILE_ABSENT,
                        confidence=EvidenceConfidence.HIGH,
                        explanation="absent",
                        artifact_path="x",
                    ),
                ),
            ),
            ScanOutcome("alternate_data_streams", AnalysisState.UNAVAILABLE),
        )
    )

    restored = json.loads(canonicalize(report.to_dict()).decode("utf-8"))

    assert restored["coverage"] == AnalysisState.PARTIAL.name
    assert restored["scanner_coverage"]["ran"] == ["path_existence"]
    assert restored["scanner_coverage"]["unavailable"] == ["alternate_data_streams"]


def test_10d_coverage_states_are_all_distinct_on_the_wire():
    """No two coverage states share a serialized name."""
    names = [state.name for state in AnalysisState]
    assert len(names) == len(set(names))
    assert "PARTIAL" in names
    assert "PERFORMED" in names
