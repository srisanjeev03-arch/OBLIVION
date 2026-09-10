"""A deterministic, dependency-free classifier: the floor to measure against.

The question Phase 27 has to answer is whether fine-tuning a language model is
worth doing. That question is meaningless without a floor. "The model scores
0.74" says nothing; "the model scores 0.74 and a hundred lines of filename rules
score 0.71" says a great deal.

So this is a real classifier, not a mock. It reads a filename and its metadata
and applies ordered rules. It is genuinely useful in its own right - a large
share of sensitive files are identifiable from their names - and it is honest
about what it cannot do: anything requiring content, context or judgement gets
``UNKNOWN`` rather than a guess.

It emits the same JSON contract a language model must emit, so it travels
through the same validation path, and its numbers are directly comparable.

It is deliberately **not** offered by ``provider_from_env``. This is a
measurement instrument, not a production AI substitute, and a rule that fires on
a filename must never be presented to an operator as though a model had reasoned
about it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Final

from oblivion.ai.provider import DEFAULT_TIMEOUT_SECONDS, AIProvider
from oblivion.ai.schema import AdvisoryKind, ModelIdentity, SensitivityClass

BASELINE_VERSION: Final = "heuristic-1"


@dataclass(frozen=True)
class Rule:
    """One filename pattern, the class it implies, and how sure that makes us.

    ``confidence`` is set from how specific the pattern is, not from how
    important the class is. A rule that fires on ``id_rsa`` is near-certain; one
    that fires on the word "report" is a hint. Inflating the second because
    business documents matter would produce exactly the overconfidence the
    calibration metric is there to catch.
    """

    pattern: re.Pattern[str]
    sensitivity: SensitivityClass
    confidence: float
    factor: str


def _rule(
    regex: str, sensitivity: SensitivityClass, confidence: float, factor: str
) -> Rule:
    return Rule(re.compile(regex, re.IGNORECASE), sensitivity, confidence, factor)


#: Ordered. The first match wins, so the most specific and most consequential
#: patterns come first: misfiling a private key as "source code" is a worse
#: error than misfiling a spreadsheet.
RULES: Final[tuple[Rule, ...]] = (
    _rule(
        r"(^|[_\-.])id_(rsa|dsa|ecdsa|ed25519)($|[_\-.])|\.pem$|\.pfx$|\.p12$"
        r"|\.keystore$|private[_\-]?key",
        SensitivityClass.AUTHENTICATION_MATERIAL,
        0.95,
        "filename matches a private-key or keystore convention",
    ),
    _rule(
        r"\.env$|(^|[_\-.])secrets?($|[_\-.])|credential|\.npmrc$|\.pgpass$"
        r"|htpasswd|(^|[_\-.])tokens?($|[_\-.])",
        SensitivityClass.CREDENTIALS,
        0.85,
        "filename matches a credentials-store convention",
    ),
    _rule(
        r"shadow$|sam$|ntds\.dit$|security\.evtx$|audit\.log$|firewall|\.reg$",
        SensitivityClass.SYSTEM_SECURITY,
        0.8,
        "filename matches a system-security artefact",
    ),
    _rule(
        r"payroll|invoice|salar|bank|iban|account[_\-]?statement|tax[_\-]?return"
        r"|ledger|transactions?",
        SensitivityClass.FINANCIAL_DATA,
        0.75,
        "filename indicates financial records",
    ),
    _rule(
        r"customer|patient|employee|personnel|hr[_\-]|passport|ssn"
        r"|national[_\-]?id|contacts?|medical",
        SensitivityClass.PERSONAL_DATA,
        0.75,
        "filename indicates records about people",
    ),
    _rule(
        r"\.(py|js|ts|tsx|jsx|java|c|cc|cpp|h|hpp|rs|go|rb|cs|kt|swift|php|sql)$",
        SensitivityClass.SOURCE_CODE,
        0.8,
        "source-code file extension",
    ),
    _rule(
        r"contract|nda|confidential|proprietary|acquisition|merger|strategy"
        r"|roadmap|board[_\-]?minutes",
        SensitivityClass.CONFIDENTIAL_BUSINESS,
        0.65,
        "filename indicates confidential business material",
    ),
    _rule(
        r"\.(txt|md|log|csv|json|xml|yaml|yml|ini|cfg)$",
        SensitivityClass.ORDINARY,
        0.45,
        "generic data or text extension with no sensitive indicator",
    ),
    _rule(
        r"\.(jpg|jpeg|png|gif|bmp|mp3|mp4|avi|mov|zip|tar|gz|iso)$",
        SensitivityClass.ORDINARY,
        0.5,
        "media or archive extension with no sensitive indicator",
    ),
)


class BaselineHeuristicProvider(AIProvider):
    """Answers advisory prompts from filename rules alone.

    Always available - it needs nothing - which is what makes it usable as a
    reproducible baseline on any machine, including CI with no GPU and no
    network.
    """

    def __init__(self) -> None:
        self._identity = ModelIdentity(
            model_id="baseline-heuristic",
            model_version=BASELINE_VERSION,
            provider="deterministic",
        )

    @property
    def identity(self) -> ModelIdentity:
        return self._identity

    def available(self) -> bool:
        return True

    def complete(
        self,
        prompt: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,  # noqa: ARG002 - provider interface
    ) -> str:
        """Answer whichever advisory kind the prompt asks for.

        The prompt is parsed rather than interpreted: the harness states the
        kind and the target name in a fixed form, so this reads them back out.
        A real model would infer them; a baseline does not need to pretend to.
        """
        kind = self._kind_from(prompt)
        target = self._value_from(prompt, "target_name")

        if kind is AdvisoryKind.SENSITIVITY_CLASSIFICATION:
            return json.dumps(self.classify(target))
        if kind is AdvisoryKind.SANITIZATION_RECOMMENDATION:
            return json.dumps(self.recommend(prompt))
        return json.dumps(self._decline(kind))

    # -- the rules -------------------------------------------------------

    def classify(self, target_name: str) -> dict[str, Any]:
        """Classify a filename, or say UNKNOWN.

        Abstaining is a first-class outcome. A rule set that guessed ORDINARY
        for everything it did not recognise would score better on a
        naming-conventional dataset and be actively harmful on a real one.
        """
        for rule in RULES:
            if rule.pattern.search(target_name):
                return {
                    "kind": AdvisoryKind.SENSITIVITY_CLASSIFICATION.value,
                    "assessment": (
                        f"Filename-based classification of {target_name!r} as "
                        f"{rule.sensitivity.value}. Based on the name alone; "
                        "no file content was examined."
                    ),
                    "confidence": rule.confidence,
                    "factors": [rule.factor],
                    "evidence_ids": [],
                    "limitations": [
                        "Deterministic filename heuristic; it examines no content "
                        "and cannot detect sensitive data under an innocuous name."
                    ],
                    "recommended_policy_id": None,
                    "sensitivity": rule.sensitivity.value,
                }

        return {
            "kind": AdvisoryKind.SENSITIVITY_CLASSIFICATION.value,
            "assessment": (
                f"No filename rule matches {target_name!r}, so the sensitivity is "
                "not established."
            ),
            "confidence": 0.2,
            "factors": ["no rule matched the filename"],
            "evidence_ids": [],
            "limitations": [
                "Deterministic filename heuristic; an unmatched name means "
                "unknown, not ordinary."
            ],
            "recommended_policy_id": None,
            "sensitivity": SensitivityClass.UNKNOWN.value,
        }

    def recommend(self, prompt: str) -> dict[str, Any]:
        """Recommend the policy that matches the requested mode and target type.

        This is not clever, and it should not be: the policy registry already
        encodes which policy fits which mode, so the baseline reads it rather
        than inventing an opinion. The policy engine checks the answer anyway.
        """
        mode = self._value_from(prompt, "mode") or "SELECTIVE_PERMANENT"
        target_type = self._value_from(prompt, "target_type") or "file"

        from oblivion.core.policy.engine import PolicyEngine

        match = next(
            (
                p.policy_id
                for p in PolicyEngine.list_policies()
                if mode in p.allowed_modes and target_type in p.allowed_target_types
            ),
            None,
        )

        return {
            "kind": AdvisoryKind.SANITIZATION_RECOMMENDATION.value,
            "assessment": (
                f"The allowlisted policy for mode {mode} on a {target_type} target "
                f"is {match}."
                if match
                else f"No allowlisted policy covers mode {mode} on a {target_type}."
            ),
            "confidence": 0.9 if match else 0.1,
            "factors": ["selected from the deterministic policy registry"],
            "evidence_ids": [],
            "limitations": [
                "Reads the policy registry; it applies no judgement about whether "
                "the requested mode is the right one."
            ],
            "recommended_policy_id": match,
            "sensitivity": None,
        }

    def _decline(self, kind: AdvisoryKind) -> dict[str, Any]:
        """Interpretation tasks need judgement this baseline does not have."""
        return {
            "kind": kind.value,
            "assessment": (
                "A deterministic filename heuristic cannot interpret findings. "
                "No interpretation is offered."
            ),
            "confidence": 0.0,
            "factors": ["baseline heuristic performs no interpretation"],
            "evidence_ids": ["baseline-no-interpretation"],
            "limitations": ["This baseline answers classification questions only."],
            "recommended_policy_id": None,
            "sensitivity": None,
        }

    # -- prompt parsing --------------------------------------------------

    @staticmethod
    def _kind_from(prompt: str) -> AdvisoryKind:
        for kind in AdvisoryKind:
            if kind.value in prompt:
                return kind
        return AdvisoryKind.SENSITIVITY_CLASSIFICATION

    @staticmethod
    def _value_from(prompt: str, field: str) -> str:
        match = re.search(rf"^{re.escape(field)}:\s*(.+)$", prompt, re.MULTILINE)
        return match.group(1).strip() if match else ""
