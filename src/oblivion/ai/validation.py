"""Turning raw model text into an advisory, or refusing to.

A language model produces text. This module is the only place that text becomes
something the rest of the system will look at, and it is deliberately
unforgiving: malformed JSON, unknown fields, hidden reasoning, claims of
authority, unsupported security claims and out-of-range confidence are all
refusals rather than things to clean up and pass along.

Refusing is safe here in a way it is not elsewhere. The advisory layer is
optional by design - the pipeline runs without it - so rejecting a bad output
costs an explanation and nothing else. Accepting one costs the property the
whole system is built to protect.

Every refusal is reported with a reason, because the Phase 27 evaluation
measures how often a model produces unacceptable output, and a rejection with no
stated cause is not a measurement.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from typing import Any, Final

from oblivion.ai.schema import (
    FORBIDDEN_AUTHORITY_FIELDS,
    FORBIDDEN_OUTPUT_FIELDS,
    Advisory,
    AdvisoryError,
    AdvisoryKind,
    AdvisoryResult,
    AIStatus,
    ModelIdentity,
    SensitivityClass,
    find_unsafe_claims,
)

logger = logging.getLogger(__name__)

#: Fields an advisory payload may contain. Anything else is refused rather than
#: ignored - a model inventing a field is a model that misunderstood the
#: contract, and silently dropping it would hide that.
ALLOWED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "kind",
        "assessment",
        "confidence",
        "factors",
        "evidence_ids",
        "limitations",
        "recommended_policy_id",
        "sensitivity",
    }
)

#: Longest acceptable free-text field. A model that returns an essay is not
#: following the contract, and unbounded text would end up in an evidence record.
MAX_TEXT_LENGTH: Final = 2000
MAX_LIST_ITEMS: Final = 20


def extract_json(raw: str) -> dict[str, Any]:
    """Find the JSON object in a model's response.

    Models routinely wrap JSON in prose or a code fence. Tolerating that is
    reasonable - it is a formatting habit, not a claim - so this locates the
    outermost braces. What it will not do is repair malformed JSON: a response
    that cannot be parsed is refused.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise AdvisoryError("Model returned no text")

    text = raw.strip()
    if text.startswith("```"):
        # Strip a fenced block, with or without a language tag.
        fenced = text.split("```")
        text = fenced[1] if len(fenced) > 1 else text
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AdvisoryError("Model response contains no JSON object")

    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AdvisoryError(f"Model response is not valid JSON: {exc}") from None

    if not isinstance(parsed, dict):
        raise AdvisoryError("Model response must be a JSON object")
    return parsed


def _clean_list(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise AdvisoryError(f"{label} must be a list of strings")
    if len(value) > MAX_LIST_ITEMS:
        raise AdvisoryError(
            f"{label} has {len(value)} items; the limit is {MAX_LIST_ITEMS}"
        )
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise AdvisoryError(f"{label} must contain only strings")
        if len(item) > MAX_TEXT_LENGTH:
            raise AdvisoryError(
                f"An item in {label} exceeds {MAX_TEXT_LENGTH} characters"
            )
        if item.strip():
            cleaned.append(item.strip())
    return tuple(cleaned)


def validate_advisory(
    raw: str,
    model: ModelIdentity,
    *,
    expected_kind: AdvisoryKind | None = None,
    now: _dt.datetime | None = None,
) -> Advisory:
    """Parse and validate one model response. Raises on anything unacceptable."""
    payload = extract_json(raw)

    hidden = sorted(set(payload) & FORBIDDEN_OUTPUT_FIELDS)
    if hidden:
        raise AdvisoryError(
            f"Model output contains hidden-reasoning field(s) {hidden}. This system "
            "records structured factors and does not store chain-of-thought."
        )

    authority = sorted(set(payload) & FORBIDDEN_AUTHORITY_FIELDS)
    if authority:
        raise AdvisoryError(
            f"Model output attempts to assert authority via {authority}. AI is "
            "advisory only: it cannot authorize, execute, name a target, or set "
            "an outcome."
        )

    unknown = sorted(set(payload) - ALLOWED_FIELDS)
    if unknown:
        raise AdvisoryError(
            f"Model output contains unrecognised field(s) {unknown}; the advisory "
            "contract is closed."
        )

    raw_kind = payload.get("kind")
    if not isinstance(raw_kind, str):
        raise AdvisoryError("Field 'kind' must be a string")
    try:
        kind = AdvisoryKind(raw_kind)
    except ValueError:
        raise AdvisoryError(
            f"Unknown advisory kind {raw_kind!r}; permitted: "
            f"{sorted(k.value for k in AdvisoryKind)}"
        ) from None

    if expected_kind is not None and kind is not expected_kind:
        raise AdvisoryError(
            f"Model answered a different question: expected {expected_kind.value}, "
            f"got {kind.value}"
        )

    assessment = payload.get("assessment")
    if not isinstance(assessment, str) or not assessment.strip():
        raise AdvisoryError("Field 'assessment' must be a non-empty string")
    if len(assessment) > MAX_TEXT_LENGTH:
        raise AdvisoryError(
            f"assessment exceeds {MAX_TEXT_LENGTH} characters; the contract asks "
            "for a concise structured answer"
        )

    confidence = payload.get("confidence", 0.0)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise AdvisoryError("Field 'confidence' must be a number between 0 and 1")
    # Deliberately not clamped. A model reporting 1.7 has misunderstood the
    # scale, and quietly turning that into 1.0 would record a confident answer
    # the model never actually expressed.
    if not 0.0 <= float(confidence) <= 1.0:
        raise AdvisoryError(
            f"confidence {confidence!r} is outside 0..1; it is refused rather than "
            "clamped, because clamping would invent a value the model did not give"
        )

    sensitivity: SensitivityClass | None = None
    raw_sensitivity = payload.get("sensitivity")
    if raw_sensitivity is not None:
        if not isinstance(raw_sensitivity, str):
            raise AdvisoryError("Field 'sensitivity' must be a string")
        try:
            sensitivity = SensitivityClass(raw_sensitivity)
        except ValueError:
            raise AdvisoryError(
                f"Unknown sensitivity {raw_sensitivity!r}; permitted: "
                f"{sorted(s.value for s in SensitivityClass)}"
            ) from None

    policy = payload.get("recommended_policy_id")
    if policy is not None and not isinstance(policy, str):
        raise AdvisoryError("Field 'recommended_policy_id' must be a string or null")

    # Advisory.__post_init__ performs the unsafe-claim check over assessment and
    # factors. Checking limitations here too: a "limitation" that asserts
    # perfection is the most confusing possible place for such a claim.
    limitations = _clean_list(payload.get("limitations"), "limitations")
    for limitation in limitations:
        if unsafe := find_unsafe_claims(limitation):
            raise AdvisoryError(
                f"A stated limitation makes an unsupported claim: {unsafe}"
            )

    return Advisory(
        kind=kind,
        assessment=assessment.strip(),
        model=model,
        generated_at=now or _dt.datetime.now(_dt.timezone.utc),
        confidence=float(confidence),
        factors=_clean_list(payload.get("factors"), "factors"),
        evidence_ids=_clean_list(payload.get("evidence_ids"), "evidence_ids"),
        limitations=limitations,
        recommended_policy_id=policy,
        sensitivity=sensitivity,
    )


def validate_or_reject(
    raw: str,
    model: ModelIdentity,
    *,
    expected_kind: AdvisoryKind | None = None,
    now: _dt.datetime | None = None,
) -> AdvisoryResult:
    """Validate, returning a ``REJECTED`` result rather than raising.

    The advisor uses this: a bad model output must not propagate an exception
    into an erasure pipeline that was going to succeed without any advisory at
    all.
    """
    try:
        advisory = validate_advisory(raw, model, expected_kind=expected_kind, now=now)
    except AdvisoryError as exc:
        logger.info("ai.output.rejected model=%s reason=%s", model.model_id, exc)
        return AdvisoryResult(
            status=AIStatus.REJECTED,
            detail="The model's output did not satisfy the advisory contract.",
            rejection_reasons=(str(exc),),
        )
    return AdvisoryResult(status=AIStatus.AVAILABLE, advisory=advisory)
