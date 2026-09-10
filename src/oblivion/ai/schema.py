"""The contract every AI output must satisfy before anything looks at it.

Two ideas shape this module.

**Advisory is structural, not a label.** :class:`Advisory` has no field that can
carry a decision. There is no ``authorized``, no ``execute``, no ``verdict``, and
``advisory`` is not settable to anything but ``True``. A model cannot express an
instruction here, so no downstream reader can mistake one for having been given.

**Some sentences are refused outright.** A model that says "guaranteed
unrecoverable" or "the NAND has been erased" is making a claim this system's own
capabilities cannot support - the privileged service performs no overwrite and
opens no raw volume handle. Such an output is rejected rather than shown with a
caveat, because a caveat next to a confident false claim is not a fix.

There is deliberately no field for reasoning, rationale, thoughts or scratchpad.
Structured ``factors`` are what a reviewer needs; hidden reasoning is not
something this system stores.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final


class AdvisoryError(Exception):
    """Raised when a model output cannot be accepted as an advisory."""


class AdvisoryKind(str, Enum):
    """What question the advisory answers."""

    SENSITIVITY_CLASSIFICATION = "SENSITIVITY_CLASSIFICATION"
    SANITIZATION_RECOMMENDATION = "SANITIZATION_RECOMMENDATION"
    RECOVERY_RISK_INTERPRETATION = "RECOVERY_RISK_INTERPRETATION"
    RESIDUAL_INTERPRETATION = "RESIDUAL_INTERPRETATION"


class SensitivityClass(str, Enum):
    """Categories from ``docs/AI.md``.

    ``UNKNOWN`` exists so a model that cannot classify something says so instead
    of guessing ``ORDINARY``, which would understate risk in exactly the cases
    where understating it matters most.
    """

    CREDENTIALS = "CREDENTIALS"
    AUTHENTICATION_MATERIAL = "AUTHENTICATION_MATERIAL"
    PERSONAL_DATA = "PERSONAL_DATA"
    FINANCIAL_DATA = "FINANCIAL_DATA"
    SOURCE_CODE = "SOURCE_CODE"
    CONFIDENTIAL_BUSINESS = "CONFIDENTIAL_BUSINESS"
    SYSTEM_SECURITY = "SYSTEM_SECURITY"
    ORDINARY = "ORDINARY"
    UNKNOWN = "UNKNOWN"


class AIStatus(str, Enum):
    """Whether an advisory was produced, and if not, why not.

    ``UNAVAILABLE`` and ``REJECTED`` are different facts. Unavailable means no
    model answered; rejected means one did and its answer was not acceptable.
    The second is a signal about the model and belongs in the evaluation
    metrics, so collapsing them would hide a real quality problem.
    """

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    REJECTED = "REJECTED"


#: Claims no component of this system can support. Matched case-insensitively
#: against the free-text fields of a model output.
#:
#: The list is drawn from what the product principle in CLAUDE.md forbids and
#: what the privileged service reports as UNAVAILABLE: no overwrite is
#: performed, no raw volume handle is opened, no physical medium is examined.
#: A model asserting otherwise is not describing this system.
UNSAFE_CLAIM_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"guarantee\w*\s+(?:\w+\s+){0,3}unrecoverab",
        r"100\s*%\s*(?:secure|safe|effective|unrecoverab|deleted|erased)",
        r"\bimpossible to recover\b",
        r"\bcannot (?:ever )?be recovered\b",
        r"\bunrecoverable by any\b",
        r"\bphysical(?:ly)? (?:erased|destroyed|sanitiz)",
        r"\bnand\b.{0,20}\b(?:erased|wiped|sanitiz)",
        r"\bmilitary[- ]grade\b",
        r"\bdod\s*5220\b",
        r"\bpermanently destroyed\b",
        r"\bforensically (?:clean|unrecoverable)\b",
        r"\bno trace (?:remains|is left)\b",
        r"\bzero (?:risk|chance) of recovery\b",
    )
)

#: Field names a model might use to smuggle hidden reasoning. Their presence is
#: an error rather than something to drop silently: a caller that sent a prompt
#: asking for reasoning should learn that the contract forbids it.
FORBIDDEN_OUTPUT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "reasoning",
        "rationale",
        "chain_of_thought",
        "thoughts",
        "thinking",
        "scratchpad",
        "internal_monologue",
        "deliberation",
        "analysis_steps",
    }
)

#: Fields that would let a model assert authority rather than offer advice.
FORBIDDEN_AUTHORITY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "authorized",
        "approve",
        "approved",
        "execute",
        "command",
        "action",
        "verdict",
        "decision",
        "certificate_result",
        "assurance_status",
        "verification_status",
        "target_path",
        "actor_id",
    }
)


def find_unsafe_claims(text: str) -> list[str]:
    """Every unsupported claim in a piece of text, named by what matched."""
    if not text:
        return []
    return [
        match.group(0)
        for pattern in UNSAFE_CLAIM_PATTERNS
        if (match := pattern.search(text)) is not None
    ]


@dataclass(frozen=True)
class ModelIdentity:
    """Which model produced an advisory.

    Recorded on every advisory so a later evaluation can attribute a bad output
    to a specific model and version rather than to "the AI".
    """

    model_id: str
    model_version: str
    provider: str

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise AdvisoryError("model_id must be non-empty")


@dataclass(frozen=True)
class Advisory:
    """One piece of advice. Never an instruction.

    ``advisory`` is a property rather than a field precisely so that no
    construction path, deserialization included, can set it to ``False``.
    """

    kind: AdvisoryKind
    assessment: str
    model: ModelIdentity
    generated_at: _dt.datetime
    confidence: float = 0.0
    factors: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    #: Only ever a *suggested* policy id. The policy engine decides whether it
    #: is allowlisted and compatible; this is an input to that check and never a
    #: substitute for it.
    recommended_policy_id: str | None = None

    sensitivity: SensitivityClass | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise AdvisoryError(
                f"confidence must be between 0 and 1, got {self.confidence!r}"
            )
        if not self.assessment.strip():
            raise AdvisoryError("assessment must be non-empty")
        if self.generated_at.tzinfo is None:
            raise AdvisoryError(
                "generated_at must be timezone-aware so advisories from different "
                "processes can be ordered"
            )

        unsafe = find_unsafe_claims(self.assessment)
        for factor in self.factors:
            unsafe.extend(find_unsafe_claims(factor))
        if unsafe:
            raise AdvisoryError(
                "Advisory makes claims this system cannot support: "
                f"{sorted(set(unsafe))}. No component performs overwrite, raw "
                "volume access or physical sanitization, so no advisory may "
                "assert them."
            )

        # An interpretation of findings must cite the findings it interpreted.
        # Without that, a reviewer cannot check the advice against anything.
        interpretive = {
            AdvisoryKind.RECOVERY_RISK_INTERPRETATION,
            AdvisoryKind.RESIDUAL_INTERPRETATION,
        }
        if self.kind in interpretive and not self.evidence_ids:
            raise AdvisoryError(
                f"{self.kind.value} must cite the evidence it interpreted; an "
                "interpretation with no referent cannot be checked."
            )

    @property
    def advisory(self) -> bool:
        """Always ``True``. There is no path that makes an advisory binding."""
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "assessment": self.assessment,
            "confidence": self.confidence,
            "factors": list(self.factors),
            "evidence_ids": list(self.evidence_ids),
            "limitations": list(self.limitations),
            "recommended_policy_id": self.recommended_policy_id,
            "sensitivity": self.sensitivity.value if self.sensitivity else None,
            "model_id": self.model.model_id,
            "model_version": self.model.model_version,
            "provider": self.model.provider,
            "generated_at": self.generated_at.isoformat(),
            "advisory": True,
        }


@dataclass(frozen=True)
class AdvisoryResult:
    """What the advisor produced, or why it produced nothing.

    The pipeline must be able to continue on any of these, so the absence of an
    advisory is a first-class value rather than an exception.
    """

    status: AIStatus
    advisory: Advisory | None = None
    detail: str = ""
    rejection_reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status is AIStatus.AVAILABLE and self.advisory is None:
            raise AdvisoryError("An AVAILABLE result must carry an advisory")
        if self.status is not AIStatus.AVAILABLE and self.advisory is not None:
            raise AdvisoryError(
                f"A {self.status.value} result must not carry an advisory; a "
                "rejected or unavailable output has nothing usable in it."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "detail": self.detail,
            "rejection_reasons": list(self.rejection_reasons),
            "advisory": self.advisory.to_dict() if self.advisory else None,
        }
