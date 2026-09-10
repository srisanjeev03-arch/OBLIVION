"""Deterministic, fail-closed rules for assurance assessment.

The rule answers one question: *what does the collected evidence support?*

The distinction that matters is between a finding and a fact about the search.
An empty list of residual findings is produced both by "the target was scanned
and nothing was found" and by "nothing was ever scanned". A rule that reads only
the findings cannot tell those apart, and will report success for an operation
that was never examined. That is what :class:`EvidenceCoverage` exists to
prevent: the caller must state which analyses actually ran, and absence of that
statement is treated as absence of evidence.
"""

from dataclasses import dataclass, field

from .models import (
    RECOVERY_DATA_WAS_RECOVERED,
    RECOVERY_TEST_INCONCLUSIVE,
    AnalysisState,
    AssuranceConfidence,
    AssuranceStatus,
    EvidenceCoverage,
    InconclusiveReason,
    RecoveryTestResult,
    ResidualFinding,
)

#: Human-readable explanation for each way a required analysis can fall short.
_SHORTFALL_DESCRIPTION = {
    AnalysisState.NOT_PERFORMED: "was not performed",
    AnalysisState.UNAVAILABLE: "could not be performed in this environment",
    AnalysisState.INCONCLUSIVE: "ran but reached no determination",
}


@dataclass
class RuleEvaluation:
    """Outcome of a rule, including why a determination could not be reached."""

    status: AssuranceStatus
    confidence: AssuranceConfidence
    summary: str
    inconclusive_reasons: list[InconclusiveReason] = field(default_factory=list)


class AssuranceRule:
    """Base class for assurance evaluation rules."""

    def evaluate(
        self,
        residual_findings: list[ResidualFinding],
        recovery_results: list[RecoveryTestResult],
        coverage: EvidenceCoverage | None = None,
    ) -> RuleEvaluation:
        raise NotImplementedError


class DefaultAssuranceRule(AssuranceRule):
    """The default evidence-bounded rule.

    Evaluation order, and why it is this order:

    1. **Conclusive negatives first.** A recovery test that recovered the target,
       or a critical residual artifact, is direct positive evidence that the data
       survived. That conclusion does not depend on how complete the rest of the
       evidence is, so it is reported even when coverage is incomplete.
    2. **Coverage gate.** Beyond that point every remaining verdict is a claim
       about what was *not* found, which is only meaningful if the search
       actually happened. Any required analysis that did not run makes the
       result ``INCONCLUSIVE``.
    3. **Corroboration.** A caller may declare that recovery testing ran; if it
       produced no results at all, the declaration is unsubstantiated and the
       result is ``INCONCLUSIVE`` rather than trusted.
    4. **Residual artifacts** that are present but not critical are ``PARTIAL``.
    5. **Only then** may the result be ``PASSED``.

    ``PASSED`` therefore asserts something narrow and true: the required analyses
    ran, the recovery test did not recover the target within its supported scope,
    and no residual artifacts were found within the configured scan scope. It is
    never a claim of irrecoverability.
    """

    def evaluate(
        self,
        residual_findings: list[ResidualFinding],
        recovery_results: list[RecoveryTestResult],
        coverage: EvidenceCoverage | None = None,
    ) -> RuleEvaluation:
        # A caller that says nothing about coverage has proved nothing.
        coverage = coverage if coverage is not None else EvidenceCoverage()

        # 1. Conclusive negatives - independent of coverage completeness.
        for result in recovery_results:
            if result.status == RECOVERY_DATA_WAS_RECOVERED:
                return RuleEvaluation(
                    AssuranceStatus.FAILED,
                    AssuranceConfidence.HIGH,
                    f"Recovery test {result.test_id} recovered the target: data is recoverable.",
                )

        critical = [f for f in residual_findings if f.severity == "CRITICAL"]
        if critical:
            return RuleEvaluation(
                AssuranceStatus.FAILED,
                AssuranceConfidence.HIGH,
                f"Critical residual artifacts found ({len(critical)}).",
            )

        # 2. Coverage gate - no positive claim without a completed search.
        shortfalls = coverage.shortfalls()
        if shortfalls:
            reasons = [
                InconclusiveReason(
                    reason_code=f"{name.upper()}_{state.name}",
                    description=(
                        f"{name.replace('_', ' ').capitalize()} "
                        f"{_SHORTFALL_DESCRIPTION[state]}."
                    ),
                    context={"analysis": name, "state": state.name},
                )
                for name, state in shortfalls
            ]
            missing = ", ".join(name.replace("_", " ") for name, _ in shortfalls)
            return RuleEvaluation(
                AssuranceStatus.INCONCLUSIVE,
                AssuranceConfidence.LOW,
                (
                    "Assurance is inconclusive: required evidence is missing "
                    f"({missing}). Absence of findings is not evidence of erasure."
                ),
                reasons,
            )

        # 3. Corroboration - a declared recovery test must have produced results.
        if not recovery_results:
            return RuleEvaluation(
                AssuranceStatus.INCONCLUSIVE,
                AssuranceConfidence.LOW,
                (
                    "Assurance is inconclusive: recovery testing was declared "
                    "performed but reported no results."
                ),
                [
                    InconclusiveReason(
                        reason_code="RECOVERY_TEST_NO_RESULTS",
                        description=(
                            "Coverage declared recovery testing performed, but no "
                            "recovery test result was supplied."
                        ),
                    )
                ],
            )

        inconclusive_tests = [
            r for r in recovery_results if r.status == RECOVERY_TEST_INCONCLUSIVE
        ]
        if inconclusive_tests:
            return RuleEvaluation(
                AssuranceStatus.INCONCLUSIVE,
                AssuranceConfidence.LOW,
                (
                    "Assurance is inconclusive: "
                    f"{len(inconclusive_tests)} recovery test(s) reached no determination."
                ),
                [
                    InconclusiveReason(
                        reason_code="RECOVERY_TEST_INCONCLUSIVE",
                        description=f"Recovery test {r.test_id} was inconclusive.",
                        context={"test_id": r.test_id},
                    )
                    for r in inconclusive_tests
                ],
            )

        # 4. Residual artifacts present, none critical.
        if residual_findings:
            return RuleEvaluation(
                AssuranceStatus.PARTIAL,
                AssuranceConfidence.MEDIUM,
                f"Residual artifacts found ({len(residual_findings)}), none critical.",
            )

        # 5. Every required analysis ran and none of them contradicted erasure.
        return RuleEvaluation(
            AssuranceStatus.PASSED,
            AssuranceConfidence.HIGH,
            (
                "Residual analysis and recovery testing were both performed. "
                "Recovery was not successful within the supported test scope and "
                "no residual artifacts were found within the configured scan scope."
            ),
        )
