"""The advisory layer's single entry point.

Everything the AI can do goes through this class, and the class has no method
that changes anything. It classifies, it interprets, and it suggests a policy -
and a suggestion is run past :class:`PolicyEngine` here, in this module, before
it is passed on, so a suggested policy that is not allowlisted or not compatible
with the operation never leaves as advice.

The required boundary is:

    AI → Recommendation → Policy Engine → Safety Validator → Authorization
       → Human Confirmation → Deterministic Execution

This module implements the first two arrows and hands off. It imports nothing
that can delete, and nothing that can authorize; the test suite asserts that by
scanning this package's imports, because a comment saying "does not execute" is
worth less than an import graph that cannot.

Prompts state the constraints the validator will enforce. That is not a
substitute for validation - a model can ignore any instruction - but a model
told the rules up front produces acceptable output far more often, and the
rejection rate is what Phase 27 measures.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from oblivion.ai.provider import AIProvider, NullProvider, ProviderError
from oblivion.ai.schema import Advisory, AdvisoryKind, AdvisoryResult, AIStatus
from oblivion.ai.validation import validate_or_reject
from oblivion.core.policy.engine import PolicyEngine, PolicyError

logger = logging.getLogger(__name__)

#: Prepended to every prompt. States the contract and the refusals, in the
#: model's own working context, so acceptable output is the path of least
#: resistance rather than something only the validator insists on.
SYSTEM_RULES = """\
You are an advisory component in a data-erasure system. You never authorize,
execute, or decide anything. A deterministic policy engine makes all decisions.

Answer ONLY with a single JSON object, with these fields and no others:
  kind, assessment, confidence, factors, evidence_ids, limitations,
  recommended_policy_id, sensitivity

Rules:
- confidence is a number between 0 and 1.
- Do NOT include reasoning, rationale, chain_of_thought, or any similar field.
- Do NOT include authorized, execute, verdict, decision, target_path or actor_id.
- NEVER claim data is guaranteed unrecoverable, 100% erased, physically or NAND
  erased, or impossible to recover. This system performs logical deletion only:
  it does no overwrite, opens no raw volume handle, and examines no physical
  medium. A recovery method finding nothing is evidence about that method only.
- When you interpret findings, cite their identifiers in evidence_ids.
- If you cannot determine something, say so and use the UNKNOWN category.
"""


class SecurityAdvisor:
    """Produces advisories. Cannot produce decisions.

    Every method returns an :class:`AdvisoryResult`, never a bare value, so a
    caller must confront the ``UNAVAILABLE`` and ``REJECTED`` cases rather than
    receiving something that looks usable.
    """

    def __init__(self, provider: AIProvider | None = None) -> None:
        self._provider = provider or NullProvider()

    @property
    def provider(self) -> AIProvider:
        return self._provider

    @property
    def available(self) -> bool:
        return self._provider.available()

    def _ask(self, prompt: str, kind: AdvisoryKind) -> AdvisoryResult:
        """Send one prompt and validate the answer.

        Provider failure is reported as ``UNAVAILABLE`` rather than raised. The
        pipeline that may be calling this is mid-operation, and an advisory
        failing must never be able to fail an erasure that was otherwise sound.
        """
        if not self._provider.available():
            return AdvisoryResult(
                status=AIStatus.UNAVAILABLE,
                detail=self._provider.unavailable_reason,
            )

        try:
            raw = self._provider.complete(f"{SYSTEM_RULES}\n{prompt}")
        except ProviderError as exc:
            logger.info("ai.provider.failed reason=%s", exc)
            return AdvisoryResult(
                status=AIStatus.UNAVAILABLE,
                detail=f"The model was reachable but did not answer: {exc}",
            )
        except Exception as exc:  # noqa: BLE001 - must not break an operation
            logger.exception("ai.provider.unexpected_failure")
            return AdvisoryResult(
                status=AIStatus.UNAVAILABLE,
                detail=f"The AI provider raised {type(exc).__name__}.",
            )

        return validate_or_reject(raw, self._provider.identity, expected_kind=kind)

    # -- the four things the AI is allowed to do -------------------------

    def classify_sensitivity(
        self, *, target_name: str, metadata: dict[str, Any] | None = None
    ) -> AdvisoryResult:
        """Suggest how sensitive a target is.

        Only metadata is sent - the name, size and type. File *contents* are
        never sent to a model: that would put the very data the system was asked
        to erase into a third component, which is the opposite of the job.
        """
        prompt = (
            f"kind must be {AdvisoryKind.SENSITIVITY_CLASSIFICATION.value}.\n"
            "Classify the sensitivity of a target from its metadata alone.\n"
            f"target_name: {target_name}\n"
            f"metadata: {json.dumps(metadata or {}, default=str)[:1500]}\n"
        )
        return self._ask(prompt, AdvisoryKind.SENSITIVITY_CLASSIFICATION)

    def recommend_policy(
        self,
        *,
        target_name: str,
        target_type: str,
        mode: str,
        available_policies: list[str] | None = None,
    ) -> AdvisoryResult:
        """Suggest a policy, then check the suggestion against the policy engine.

        This is where the AI-to-policy arrow is enforced. A model naming a policy
        that is not allowlisted, or not compatible with this mode and target
        type, has its recommendation rejected here - so an unusable suggestion
        never reaches a human as though it were actionable.
        """
        policies = available_policies or [
            p.policy_id for p in PolicyEngine.list_policies()
        ]
        prompt = (
            f"kind must be {AdvisoryKind.SANITIZATION_RECOMMENDATION.value}.\n"
            "Recommend one policy id from this list, and only from this list:\n"
            f"{json.dumps(policies)}\n"
            f"target_name: {target_name}\ntarget_type: {target_type}\nmode: {mode}\n"
        )
        result = self._ask(prompt, AdvisoryKind.SANITIZATION_RECOMMENDATION)

        if result.status is not AIStatus.AVAILABLE or result.advisory is None:
            return result

        suggested = result.advisory.recommended_policy_id
        if suggested is None:
            return result

        try:
            PolicyEngine.validate_operation_policy(suggested, mode, target_type)
        except PolicyError as exc:
            return AdvisoryResult(
                status=AIStatus.REJECTED,
                detail=(
                    "The model recommended a policy the policy engine will not "
                    "accept. The deterministic engine is authoritative; the "
                    "recommendation is discarded rather than shown as actionable."
                ),
                rejection_reasons=(str(exc),),
            )
        return result

    def interpret_recovery_risk(
        self, *, recovery_report: dict[str, Any], evidence_ids: list[str]
    ) -> AdvisoryResult:
        """Explain what the recovery results mean, in plain language.

        The prompt hands the model the report's own scope note, which states
        that no combination of these results establishes universal
        irrecoverability. The validator enforces it either way.
        """
        prompt = (
            f"kind must be {AdvisoryKind.RECOVERY_RISK_INTERPRETATION.value}.\n"
            "Explain the residual recovery risk implied by these results. Each "
            "result describes only the method that produced it.\n"
            f"evidence_ids to cite: {json.dumps(evidence_ids)}\n"
            f"recovery_report: {json.dumps(recovery_report, default=str)[:1500]}\n"
        )
        return self._ask(prompt, AdvisoryKind.RECOVERY_RISK_INTERPRETATION)

    def interpret_residuals(
        self, *, residual_report: dict[str, Any], evidence_ids: list[str]
    ) -> AdvisoryResult:
        """Explain the significance of residual findings."""
        prompt = (
            f"kind must be {AdvisoryKind.RESIDUAL_INTERPRETATION.value}.\n"
            "Explain what these residual findings mean and why they matter.\n"
            f"evidence_ids to cite: {json.dumps(evidence_ids)}\n"
            f"residual_report: {json.dumps(residual_report, default=str)[:1500]}\n"
        )
        return self._ask(prompt, AdvisoryKind.RESIDUAL_INTERPRETATION)


def apply_is_not_supported(advisory: Advisory) -> None:
    """There is no function that acts on an advisory, and this documents that.

    Kept as a named, raising stub so the absence is discoverable. Someone
    searching this package for a way to execute a recommendation finds this and
    its explanation, rather than concluding they simply have not found the right
    method yet.
    """
    raise NotImplementedError(
        "Advisories are never applied automatically. A recommendation becomes an "
        "operation only by passing through the policy engine, safety validation, "
        "authorization and human confirmation - none of which this package can "
        "perform or bypass."
    )
