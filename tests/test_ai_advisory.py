"""Phase 26: the AI is advisory, and the tests are what make that true.

A docstring promising that a component cannot execute anything is worth very
little. These tests check the property structurally: the package's import graph
contains nothing that can delete or authorize, the advisory type has no field
that can carry a decision, and every unsafe or malformed output is refused with
a stated reason.

No model is contacted. ``StaticProvider`` returns fixed strings, which exercises
the entire validation path deterministically - which is exactly what a security
property needs, and what a live model could never give.
"""

from __future__ import annotations

import ast
import datetime as _dt
import inspect
import json
from pathlib import Path

import pytest

from oblivion.ai import (
    SYSTEM_RULES,
    Advisory,
    AdvisoryError,
    AdvisoryKind,
    AIStatus,
    LocalQwenProvider,
    ModelIdentity,
    NullProvider,
    SecurityAdvisor,
    SensitivityClass,
    StaticProvider,
    find_unsafe_claims,
    provider_from_env,
    validate_advisory,
    validate_or_reject,
)
from oblivion.ai.advisor import apply_is_not_supported

MODEL = ModelIdentity(model_id="test-model", model_version="1", provider="static")
SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"


def advisory_json(**overrides) -> str:
    payload = {
        "kind": AdvisoryKind.SENSITIVITY_CLASSIFICATION.value,
        "assessment": "The filename suggests customer records.",
        "confidence": 0.7,
        "factors": ["filename contains 'customer'", "csv extension"],
        "evidence_ids": [],
        "limitations": ["Classification is based on metadata only."],
        "recommended_policy_id": None,
        "sensitivity": SensitivityClass.PERSONAL_DATA.value,
    }
    payload.update(overrides)
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# The boundary, asserted structurally
# ---------------------------------------------------------------------------


def test_the_ai_package_imports_nothing_that_can_execute():
    """The strongest form of "AI cannot reach destructive execution".

    A comment can claim it; an import graph can enforce it. The advisory package
    may import the policy engine - it must, to check a recommendation - but
    nothing that erases, nothing privileged, and nothing that authorizes.
    """
    package = Path(__file__).resolve().parents[1] / "src" / "oblivion" / "ai"
    forbidden = (
        "oblivion.core.erasure",
        "oblivion.privileged",
        "oblivion.core.pipeline",
        "oblivion.core.auth",
        "oblivion.certificate.issuer",
        "oblivion.persistence",
        "subprocess",
        "os.system",
    )

    offences: list[str] = []
    for source_file in package.glob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                for banned in forbidden:
                    if name == banned or name.startswith(f"{banned}."):
                        offences.append(f"{source_file.name} imports {name}")

    assert not offences, f"AI package can reach execution: {offences}"


def test_there_is_no_way_to_apply_an_advisory():
    """The absence is discoverable rather than merely true."""
    advisory = validate_advisory(advisory_json(), MODEL)
    with pytest.raises(NotImplementedError, match="never applied automatically"):
        apply_is_not_supported(advisory)


def test_an_advisory_is_always_advisory():
    """No construction path can make it binding."""
    advisory = validate_advisory(advisory_json(), MODEL)
    assert advisory.advisory is True
    assert advisory.to_dict()["advisory"] is True

    with pytest.raises((AttributeError, TypeError)):
        advisory.advisory = False  # type: ignore[misc]


def test_a_model_cannot_assert_authority():
    """Fields that would express a decision are refused, not ignored."""
    for field in (
        "authorized",
        "execute",
        "verdict",
        "decision",
        "target_path",
        "actor_id",
        "assurance_status",
    ):
        with pytest.raises(AdvisoryError, match="assert authority"):
            validate_advisory(advisory_json(**{field: "anything"}), MODEL)


def test_a_model_cannot_store_hidden_reasoning():
    for field in ("reasoning", "chain_of_thought", "thoughts", "scratchpad"):
        with pytest.raises(AdvisoryError, match="hidden-reasoning"):
            validate_advisory(advisory_json(**{field: "step 1..."}), MODEL)


# ---------------------------------------------------------------------------
# Unsafe claims
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        "The data is guaranteed unrecoverable.",
        "This achieves 100% secure deletion.",
        "It is impossible to recover the file now.",
        "The NAND cells were erased.",
        "The file was physically destroyed.",
        "This is military-grade erasure.",
        "The data cannot be recovered.",
        "No trace remains on the drive.",
        "There is zero chance of recovery.",
        "The disk is now forensically clean.",
    ],
)
def test_unsupported_claims_are_refused(claim):
    """The claims this system's own capabilities cannot support.

    Refused outright rather than shown with a caveat: a caveat beside a
    confident false statement does not undo it.
    """
    assert find_unsafe_claims(claim), f"{claim!r} should be detected"
    with pytest.raises(AdvisoryError, match="cannot support"):
        validate_advisory(advisory_json(assessment=claim), MODEL)


def test_an_unsafe_claim_in_a_factor_is_also_refused():
    with pytest.raises(AdvisoryError, match="cannot support"):
        validate_advisory(advisory_json(factors=["deletion is 100% effective"]), MODEL)


def test_an_unsafe_claim_inside_a_limitation_is_refused():
    """The most confusing possible place for such a claim."""
    with pytest.raises(AdvisoryError, match="unsupported claim"):
        validate_advisory(
            advisory_json(limitations=["None; the data is impossible to recover."]),
            MODEL,
        )


def test_accurate_scoped_language_is_accepted():
    """The correct way to say it must remain sayable.

    A validator that rejected honest phrasing too would push authors toward
    vagueness, so this pins that scoped, accurate language passes.
    """
    advisory = validate_advisory(
        advisory_json(
            assessment=(
                "Filesystem enumeration did not reach the content. This describes "
                "that method only; carving and journal analysis were not attempted."
            )
        ),
        MODEL,
    )
    assert advisory.assessment.startswith("Filesystem enumeration")


# ---------------------------------------------------------------------------
# Malformed output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not json at all",
        "{",
        "[1, 2, 3]",
        '{"kind": 42}',
        '{"kind": "NOT_A_KIND", "assessment": "x"}',
        '{"kind": "SENSITIVITY_CLASSIFICATION"}',
        '{"kind": "SENSITIVITY_CLASSIFICATION", "assessment": ""}',
    ],
)
def test_malformed_output_never_yields_an_advisory(raw):
    result = validate_or_reject(raw, MODEL)
    assert result.status is AIStatus.REJECTED
    assert result.advisory is None
    assert result.rejection_reasons


def test_json_wrapped_in_prose_or_a_fence_is_accepted():
    """A formatting habit is not a claim, so it is tolerated - but not repaired."""
    fenced = f"```json\n{advisory_json()}\n```"
    prose = f"Here is my answer:\n{advisory_json()}\nHope that helps."

    for raw in (fenced, prose):
        assert validate_or_reject(raw, MODEL).status is AIStatus.AVAILABLE


def test_confidence_outside_the_range_is_refused_not_clamped():
    """Clamping would record a confidence the model never expressed."""
    for value in (1.7, -0.2, 42):
        result = validate_or_reject(advisory_json(confidence=value), MODEL)
        assert result.status is AIStatus.REJECTED
        assert "clamped" in " ".join(result.rejection_reasons)


def test_an_unknown_field_is_refused():
    result = validate_or_reject(advisory_json(extra_field="surprise"), MODEL)
    assert result.status is AIStatus.REJECTED
    assert "unrecognised field" in " ".join(result.rejection_reasons)


def test_answering_a_different_question_is_refused():
    result = validate_or_reject(
        advisory_json(
            kind=AdvisoryKind.RESIDUAL_INTERPRETATION.value, evidence_ids=["e1"]
        ),
        MODEL,
        expected_kind=AdvisoryKind.SENSITIVITY_CLASSIFICATION,
    )
    assert result.status is AIStatus.REJECTED


def test_an_interpretation_must_cite_its_evidence():
    """An interpretation with no referent cannot be checked by anyone."""
    with pytest.raises(AdvisoryError, match="must cite the evidence"):
        Advisory(
            kind=AdvisoryKind.RESIDUAL_INTERPRETATION,
            assessment="These findings look minor.",
            model=MODEL,
            generated_at=_dt.datetime.now(_dt.timezone.utc),
            evidence_ids=(),
        )


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_with_no_provider_the_advisor_is_unavailable_and_does_not_raise():
    """The pipeline must be able to continue safely without AI."""
    advisor = SecurityAdvisor()
    result = advisor.classify_sensitivity(target_name="customers.csv")

    assert advisor.available is False
    assert result.status is AIStatus.UNAVAILABLE
    assert result.advisory is None
    assert result.detail


def test_a_provider_that_fails_reports_unavailable_rather_than_raising():
    """An advisory failing must never fail an erasure that was otherwise sound."""
    advisor = SecurityAdvisor(StaticProvider("", fail=True))
    result = advisor.classify_sensitivity(target_name="x.txt")

    assert result.status is AIStatus.UNAVAILABLE
    assert result.advisory is None


def test_unavailable_and_rejected_are_different_facts():
    """One says no model answered; the other says a model answered badly."""
    unavailable = SecurityAdvisor(NullProvider()).classify_sensitivity(
        target_name="x.txt"
    )
    rejected = SecurityAdvisor(StaticProvider("garbage")).classify_sensitivity(
        target_name="x.txt"
    )

    assert unavailable.status is AIStatus.UNAVAILABLE
    assert rejected.status is AIStatus.REJECTED
    assert rejected.rejection_reasons


def test_an_unconfigured_deployment_gets_a_null_provider():
    provider = provider_from_env({})
    assert provider.available() is False
    assert "no ai provider is configured" in provider.unavailable_reason.lower()


def test_an_unknown_provider_never_silently_substitutes_another_model():
    provider = provider_from_env({"OBLIVION_AI_PROVIDER": "some-other-llm"})
    assert provider.available() is False
    assert "Unknown AI provider" in provider.unavailable_reason


def test_the_local_model_is_unavailable_without_weights(tmp_path):
    """Capability-driven, not assumed. No model on this machine, so: unavailable."""
    provider = LocalQwenProvider(model_path=str(tmp_path / "nope.gguf"))
    assert provider.available() is False
    assert "weights" in provider.unavailable_reason.lower()


def test_the_local_provider_imports_without_an_ml_stack():
    """This file must be importable on a machine with no ML dependencies.

    It is - this test is running.
    """
    provider = LocalQwenProvider(model_path="")
    assert provider.available() is False
    assert provider.identity.provider == "local-qwen"


# ---------------------------------------------------------------------------
# Recommendations pass through the policy engine
# ---------------------------------------------------------------------------


def test_a_valid_recommendation_survives_the_policy_check():
    response = advisory_json(
        kind=AdvisoryKind.SANITIZATION_RECOMMENDATION.value,
        recommended_policy_id=SELECTIVE_POLICY,
        sensitivity=None,
    )
    result = SecurityAdvisor(StaticProvider(response)).recommend_policy(
        target_name="notes.txt", target_type="file", mode="SELECTIVE_PERMANENT"
    )

    assert result.status is AIStatus.AVAILABLE
    assert result.advisory is not None
    assert result.advisory.recommended_policy_id == SELECTIVE_POLICY


def test_a_recommendation_the_policy_engine_rejects_is_discarded():
    """The deterministic engine is authoritative, and this is where that bites."""
    response = advisory_json(
        kind=AdvisoryKind.SANITIZATION_RECOMMENDATION.value,
        recommended_policy_id="ERASURE.INVENTED.BY.THE.MODEL.V1",
        sensitivity=None,
    )
    result = SecurityAdvisor(StaticProvider(response)).recommend_policy(
        target_name="notes.txt", target_type="file", mode="SELECTIVE_PERMANENT"
    )

    assert result.status is AIStatus.REJECTED
    assert result.advisory is None
    assert "not allowlisted" in " ".join(result.rejection_reasons)


def test_a_policy_incompatible_with_the_mode_is_discarded():
    """Allowlisted is not the same as applicable."""
    response = advisory_json(
        kind=AdvisoryKind.SANITIZATION_RECOMMENDATION.value,
        recommended_policy_id="ERASURE.LOGICAL.TREE.V1",
        sensitivity=None,
    )
    result = SecurityAdvisor(StaticProvider(response)).recommend_policy(
        target_name="notes.txt", target_type="file", mode="SELECTIVE_PERMANENT"
    )

    assert result.status is AIStatus.REJECTED


# ---------------------------------------------------------------------------
# What the advisor sends
# ---------------------------------------------------------------------------


def test_file_contents_are_never_sent_to_a_model():
    """Sending the data being erased to a model would be the opposite of the job.

    The classifier's signature accepts a name and metadata, and there is no
    parameter through which contents could be passed.
    """
    signature = inspect.signature(SecurityAdvisor.classify_sensitivity)
    assert set(signature.parameters) == {"self", "target_name", "metadata"}


def test_the_prompt_states_the_refusals_the_validator_enforces():
    """Belt and braces: told up front, and enforced regardless."""
    lowered = SYSTEM_RULES.lower()
    assert "never authorize" in lowered
    assert "chain_of_thought" in lowered
    assert "logical deletion only" in lowered
    assert "guaranteed unrecoverable" in lowered
