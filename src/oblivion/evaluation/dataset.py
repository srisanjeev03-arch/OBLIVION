"""The evaluation dataset: what we ask a model, and what a good answer is.

Format is JSONL - one case per line - chosen because it diffs cleanly, appends
without rewriting, and can be reviewed in a pull request. A dataset that is hard
to review is a dataset nobody checks, and an unchecked dataset silently defines
what "good" means.

Every case carries an ``adversarial`` flag. Adversarial cases are not there to
make the numbers look worse; they are the cases that matter most, because they
are where a model is most likely to produce a confident, plausible, unsafe
answer. They are reported separately for exactly that reason.

Cases are validated on load. A dataset with a typo'd expected label would
silently penalise a model for being right, so a malformed case is an error
rather than something to skip.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from oblivion.ai.schema import AdvisoryKind, SensitivityClass

#: Where the checked-in datasets live, relative to the repository root.
DATASET_DIRECTORY: Final = "evaluation/datasets"


class DatasetError(Exception):
    """Raised when a dataset case is malformed."""


@dataclass(frozen=True)
class EvalCase:
    """One question, and the answer a correct model would give.

    ``expected_sensitivity`` may be ``None`` for cases where no single label is
    right - the point of those cases is usually the *safety* behaviour, not the
    classification.
    """

    case_id: str
    kind: AdvisoryKind
    target_name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    expected_sensitivity: SensitivityClass | None = None
    expected_policy_id: str | None = None
    target_type: str = "file"
    mode: str = "SELECTIVE_PERMANENT"

    #: True when the case is designed to bait an unsafe or overconfident answer.
    adversarial: bool = False

    #: Why this case exists. Kept in the data so a reviewer can tell whether a
    #: failure is a real weakness or a disputed label.
    note: str = ""

    @classmethod
    def from_dict(cls, payload: Any, *, source: str = "<inline>") -> EvalCase:
        if not isinstance(payload, dict):
            raise DatasetError(f"{source}: each case must be a JSON object")

        case_id = payload.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise DatasetError(f"{source}: case_id must be a non-empty string")

        try:
            kind = AdvisoryKind(payload.get("kind", ""))
        except ValueError:
            raise DatasetError(
                f"{source}: case {case_id} has unknown kind {payload.get('kind')!r}"
            ) from None

        target_name = payload.get("target_name")
        if not isinstance(target_name, str) or not target_name.strip():
            raise DatasetError(f"{source}: case {case_id} needs a target_name")

        expected_sensitivity: SensitivityClass | None = None
        raw_sensitivity = payload.get("expected_sensitivity")
        if raw_sensitivity is not None:
            try:
                expected_sensitivity = SensitivityClass(raw_sensitivity)
            except ValueError:
                raise DatasetError(
                    f"{source}: case {case_id} expects unknown sensitivity "
                    f"{raw_sensitivity!r}. A typo here would penalise a model for "
                    "being right."
                ) from None

        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise DatasetError(f"{source}: case {case_id} metadata must be an object")

        return cls(
            case_id=case_id,
            kind=kind,
            target_name=target_name,
            metadata=metadata,
            expected_sensitivity=expected_sensitivity,
            expected_policy_id=payload.get("expected_policy_id"),
            target_type=payload.get("target_type", "file"),
            mode=payload.get("mode", "SELECTIVE_PERMANENT"),
            adversarial=bool(payload.get("adversarial", False)),
            note=payload.get("note", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "kind": self.kind.value,
            "target_name": self.target_name,
            "metadata": self.metadata,
            "expected_sensitivity": (
                self.expected_sensitivity.value if self.expected_sensitivity else None
            ),
            "expected_policy_id": self.expected_policy_id,
            "target_type": self.target_type,
            "mode": self.mode,
            "adversarial": self.adversarial,
            "note": self.note,
        }


@dataclass(frozen=True)
class EvalDataset:
    """A named, versioned set of cases.

    The name and version travel into the report, because a metric is meaningless
    without knowing what it was measured on.
    """

    name: str
    version: str
    cases: tuple[EvalCase, ...]

    #: Reasons a score on this dataset may mean less than it appears to. Written
    #: in the data file as ``# caveat: ...`` lines so they are reviewed with the
    #: cases, and copied into every report so a number is never read without the
    #: qualification that belongs to it.
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for case in self.cases:
            if case.case_id in seen:
                raise DatasetError(
                    f"Duplicate case_id {case.case_id!r}: a repeated case would be "
                    "counted twice and quietly weight the metrics"
                )
            seen.add(case.case_id)

    def __len__(self) -> int:
        return len(self.cases)

    @property
    def adversarial_cases(self) -> tuple[EvalCase, ...]:
        return tuple(c for c in self.cases if c.adversarial)

    def of_kind(self, kind: AdvisoryKind) -> tuple[EvalCase, ...]:
        return tuple(c for c in self.cases if c.kind is kind)

    @classmethod
    def from_jsonl(
        cls, path: str | Path, *, name: str = "", version: str = ""
    ) -> EvalDataset:
        """Load a dataset from a JSONL file.

        Blank lines and ``#`` comment lines are permitted so a dataset can be
        annotated in place - the annotations are for the humans who maintain it.
        """
        source = Path(path)
        if not source.is_file():
            raise DatasetError(f"No evaluation dataset at {source}")

        cases: list[EvalCase] = []
        caveats: list[str] = []
        for number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.strip()
            if stripped.lower().startswith("# caveat:"):
                caveats.append(stripped.split(":", 1)[1].strip())
                continue
            if not stripped or stripped.startswith("#"):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{source}:{number}: invalid JSON: {exc}") from None
            cases.append(EvalCase.from_dict(payload, source=f"{source}:{number}"))

        if not cases:
            raise DatasetError(f"{source} contains no cases")

        return cls(
            name=name or source.stem,
            version=version or "1",
            cases=tuple(cases),
            caveats=tuple(caveats),
        )
