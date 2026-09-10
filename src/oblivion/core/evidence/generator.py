"""Building evidence from an explicit context.

The generator takes everything it needs as an argument. It reads no global
state, opens no files and calls no engine: whatever the caller knows is what
gets recorded, and whatever the caller does not know is recorded as not known.

That constraint is what makes partial evidence honest. Phase 23 exists before
the recovery, residual and assurance stages are wired into the operation
pipeline, so most operations will have nothing to say about them. The generator
represents that as ``NOT_CHECKED`` or ``UNAVAILABLE`` - never as a passing
result, and never by omitting the field, because an omitted field reads as
"nothing to report" when the truth is "nothing was looked for".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .record import (
    EvidenceRecord,
    Observation,
    TargetDescriptor,
    new_evidence_id,
)


@dataclass(frozen=True)
class Unavailable:
    """Marks a stage that was attempted but could not produce a result.

    Distinct from ``None``, which means the stage was never attempted at all.
    The two become ``UNAVAILABLE`` and ``NOT_CHECKED`` respectively, and the
    difference matters to anyone reading the evidence later.
    """

    reason: str


#: What a caller may supply for an optional stage.
StageInput = dict[str, Any] | Unavailable | None


def _stage_observation(value: StageInput, stage: str) -> Observation:
    if isinstance(value, Unavailable):
        return Observation.unavailable(value.reason)
    if value is None:
        return Observation.not_checked(
            f"{stage} was not performed during this operation."
        )
    return Observation.observed(value, f"{stage} result as reported by the engine.")


@dataclass
class EvidenceGenerationContext:
    """Everything the generator is allowed to know.

    The required fields describe the operation itself. The optional stages are
    the parts of the lifecycle that Phase 25 will eventually connect; until then
    they are legitimately absent, and leaving them at their defaults produces
    accurate evidence rather than incomplete-looking evidence.
    """

    operation_id: str
    target: TargetDescriptor
    method: str

    policy_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    #: Result of the erasure/execution step, when one ran.
    execution_result: StageInput = None
    #: Pre-operation baseline capture.
    baseline: StageInput = None
    #: Post-operation verification (did the target stop existing?).
    verification_result: StageInput = None
    #: Recovery testing. Absent in Phase 23.
    recovery_test_result: StageInput = None
    #: Residual analysis. Absent in Phase 23.
    residual_result: StageInput = None
    #: Assurance assessment. Absent in Phase 23.
    assurance_result: StageInput = None

    #: Scope caveats that apply to this operation, e.g. logical-deletion-only.
    limitations: tuple[str, ...] = ()
    #: Preceding record in this operation's evidence chain.
    previous: EvidenceRecord | None = None
    #: Additional observations the caller measured directly.
    extra_observations: dict[str, Observation] = field(default_factory=dict)


class EvidenceGenerator:
    """Turns a context into a signable :class:`EvidenceRecord`."""

    def __init__(self, producer: str = "oblivion", producer_version: str = "0.1.0"):
        self.producer = producer
        self.producer_version = producer_version

    def generate(self, context: EvidenceGenerationContext) -> EvidenceRecord:
        """Build the record. Deterministic apart from the identifier and clock."""
        observations: dict[str, Observation] = {
            "execution": _stage_observation(context.execution_result, "Execution"),
            "baseline": _stage_observation(context.baseline, "Baseline capture"),
            "verification": _stage_observation(
                context.verification_result, "Post-operation verification"
            ),
            "recovery_test": _stage_observation(
                context.recovery_test_result, "Recovery testing"
            ),
            "residual_analysis": _stage_observation(
                context.residual_result, "Residual analysis"
            ),
            "assurance": _stage_observation(
                context.assurance_result, "Assurance assessment"
            ),
        }

        observations["policy"] = (
            Observation.observed(context.policy_id, "Server-side allowlisted policy.")
            if context.policy_id
            else Observation.not_checked("No policy identifier was supplied.")
        )
        observations["started_at"] = (
            Observation.observed(context.started_at.isoformat(), "Operation start time.")
            if context.started_at
            else Observation.not_checked("Start time was not recorded.")
        )
        observations["completed_at"] = (
            Observation.observed(
                context.completed_at.isoformat(), "Operation completion time."
            )
            if context.completed_at
            else Observation.not_checked("Completion time was not recorded.")
        )

        # Caller-measured observations are added last but may not silently
        # replace a stage the generator is responsible for.
        for name, observation in context.extra_observations.items():
            if name in observations:
                raise ValueError(
                    f"extra_observations may not override the generated "
                    f"observation {name!r}"
                )
            observations[name] = observation

        previous = context.previous
        return EvidenceRecord(
            evidence_id=new_evidence_id(),
            operation_id=context.operation_id,
            target=context.target,
            method=context.method,
            observations=observations,
            limitations=tuple(context.limitations),
            created_at=datetime.now(UTC),
            producer=self.producer,
            producer_version=self.producer_version,
            previous_evidence_id=previous.evidence_id if previous else None,
            previous_evidence_digest=previous.digest() if previous else None,
        )


__all__ = [
    "EvidenceGenerationContext",
    "EvidenceGenerator",
    "StageInput",
    "Unavailable",
]
