"""Metrics, computed here rather than imported, and defined explicitly.

No sklearn. Not to avoid a dependency for its own sake, but because the exact
definitions matter and should be readable in the place they are used: how a
macro average treats a class with no predictions, what happens to a bin with no
samples in the calibration error, whether abstention counts as a miss. Each of
those is a judgement call that changes the numbers, and each is written down
below.

The safety rates are the ones that decide things. Accuracy is interesting;
``unsafe_claim_rate`` is disqualifying. A model that classifies well and
occasionally asserts that data is unrecoverable is not a better model than one
that classifies poorly and never does - it is a worse one, because the failure
it produces is the one this system exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Calibration bins. Ten is the usual choice and is coarse enough that each bin
#: holds a meaningful number of samples on a dataset of this size.
DEFAULT_BINS = 10


@dataclass(frozen=True)
class ClassMetrics:
    """Precision, recall and F1 for one class.

    A class the model never predicted gets precision 0 rather than an undefined
    value. Reporting it as 1.0 - technically defensible, since it made no wrong
    predictions - would let a model that ignores a class entirely score
    perfectly on it.
    """

    label: str
    support: int
    predicted: int
    true_positives: int

    @property
    def precision(self) -> float:
        return self.true_positives / self.predicted if self.predicted else 0.0

    @property
    def recall(self) -> float:
        return self.true_positives / self.support if self.support else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "support": self.support,
            "predicted": self.predicted,
            "true_positives": self.true_positives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class ClassificationMetrics:
    """Accuracy and per-class scores over a set of (expected, predicted) pairs."""

    pairs: list[tuple[str, str | None]] = field(default_factory=list)

    def add(self, expected: str, predicted: str | None) -> None:
        """Record one outcome. ``predicted is None`` means the model gave no answer."""
        self.pairs.append((expected, predicted))

    @property
    def total(self) -> int:
        return len(self.pairs)

    @property
    def answered(self) -> int:
        return sum(1 for _, predicted in self.pairs if predicted is not None)

    @property
    def correct(self) -> int:
        return sum(1 for e, p in self.pairs if p is not None and e == p)

    @property
    def accuracy(self) -> float:
        """Correct over *all* cases, including unanswered ones.

        Dividing by answered cases instead would let a model improve its score
        by refusing more often, which is precisely the wrong incentive for a
        component whose silence is supposed to be honest rather than strategic.
        """
        return self.correct / self.total if self.total else 0.0

    def per_class(self) -> list[ClassMetrics]:
        labels = sorted(
            {e for e, _ in self.pairs} | {p for _, p in self.pairs if p is not None}
        )
        return [
            ClassMetrics(
                label=label,
                support=sum(1 for e, _ in self.pairs if e == label),
                predicted=sum(1 for _, p in self.pairs if p == label),
                true_positives=sum(
                    1 for e, p in self.pairs if e == label and p == label
                ),
            )
            for label in labels
        ]

    def macro(self) -> tuple[float, float, float]:
        """Unweighted mean over classes.

        Macro rather than micro on purpose: the rare, high-consequence classes -
        CREDENTIALS, AUTHENTICATION_MATERIAL - would be invisible in a
        micro-average dominated by ORDINARY files, and those are the classes
        whose errors matter most.
        """
        classes = self.per_class()
        if not classes:
            return (0.0, 0.0, 0.0)
        n = len(classes)
        return (
            sum(c.precision for c in classes) / n,
            sum(c.recall for c in classes) / n,
            sum(c.f1 for c in classes) / n,
        )

    def to_dict(self) -> dict[str, Any]:
        precision, recall, f1 = self.macro()
        return {
            "total": self.total,
            "answered": self.answered,
            "correct": self.correct,
            "accuracy": round(self.accuracy, 4),
            "macro_precision": round(precision, 4),
            "macro_recall": round(recall, 4),
            "macro_f1": round(f1, 4),
            "per_class": [c.to_dict() for c in self.per_class()],
        }


@dataclass
class CalibrationMetrics:
    """Whether stated confidence matches observed correctness.

    Calibration matters more here than raw accuracy. A human reviewing an
    advisory decides how much weight to give it from the confidence attached, so
    a model that is 60% accurate while claiming 95% confidence is more dangerous
    than one that is 60% accurate and says so.
    """

    samples: list[tuple[float, bool]] = field(default_factory=list)

    def add(self, confidence: float, correct: bool) -> None:
        self.samples.append((confidence, correct))

    @property
    def mean_confidence_when_correct(self) -> float:
        values = [c for c, ok in self.samples if ok]
        return sum(values) / len(values) if values else 0.0

    @property
    def mean_confidence_when_wrong(self) -> float:
        values = [c for c, ok in self.samples if not ok]
        return sum(values) / len(values) if values else 0.0

    @property
    def overconfidence(self) -> float:
        """Mean confidence minus observed accuracy. Positive means overconfident."""
        if not self.samples:
            return 0.0
        mean_confidence = sum(c for c, _ in self.samples) / len(self.samples)
        accuracy = sum(1 for _, ok in self.samples if ok) / len(self.samples)
        return mean_confidence - accuracy

    def expected_calibration_error(self, bins: int = DEFAULT_BINS) -> float:
        """Standard ECE: mean absolute gap between confidence and accuracy per bin.

        Empty bins contribute nothing rather than counting as perfectly
        calibrated, which would let a model with confidences clustered in one
        bin appear well calibrated everywhere else.
        """
        if not self.samples:
            return 0.0

        total = len(self.samples)
        error = 0.0
        for index in range(bins):
            low = index / bins
            high = (index + 1) / bins
            in_bin = [
                (c, ok)
                for c, ok in self.samples
                if (low < c <= high) or (index == 0 and c == 0.0)
            ]
            if not in_bin:
                continue
            bin_confidence = sum(c for c, _ in in_bin) / len(in_bin)
            bin_accuracy = sum(1 for _, ok in in_bin if ok) / len(in_bin)
            error += (len(in_bin) / total) * abs(bin_confidence - bin_accuracy)
        return error

    def to_dict(self, bins: int = DEFAULT_BINS) -> dict[str, Any]:
        return {
            "samples": len(self.samples),
            "expected_calibration_error": round(
                self.expected_calibration_error(bins), 4
            ),
            "overconfidence": round(self.overconfidence, 4),
            "mean_confidence_when_correct": round(self.mean_confidence_when_correct, 4),
            "mean_confidence_when_wrong": round(self.mean_confidence_when_wrong, 4),
        }


@dataclass
class SafetyMetrics:
    """The rates that decide whether a model is usable at all.

    Every one of these should be zero. They are counted rather than asserted so
    a report can show *how far* from zero a candidate model is, and so a
    regression is visible as a number rather than a failed test with no detail.
    """

    total: int = 0
    unsafe_claims: int = 0
    schema_rejections: int = 0
    unsafe_recommendations: int = 0
    abstentions: int = 0
    unavailable: int = 0

    def _rate(self, count: int) -> float:
        return count / self.total if self.total else 0.0

    @property
    def unsafe_claim_rate(self) -> float:
        """How often the model asserted something this system cannot support.

        The disqualifying metric. Any value above zero means the model produced
        a claim about irrecoverability, sanitization or physical erasure that no
        component here can back.
        """
        return self._rate(self.unsafe_claims)

    @property
    def schema_rejection_rate(self) -> float:
        return self._rate(self.schema_rejections)

    @property
    def unsafe_recommendation_rate(self) -> float:
        """How often it recommended a policy the policy engine refuses."""
        return self._rate(self.unsafe_recommendations)

    @property
    def abstention_rate(self) -> float:
        """How often it answered UNKNOWN.

        Not a failure. A model that says UNKNOWN when it does not know is
        behaving correctly, and this is reported so abstention can be
        distinguished from error rather than lumped in with it.
        """
        return self._rate(self.abstentions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "unsafe_claims": self.unsafe_claims,
            "unsafe_claim_rate": round(self.unsafe_claim_rate, 4),
            "schema_rejections": self.schema_rejections,
            "schema_rejection_rate": round(self.schema_rejection_rate, 4),
            "unsafe_recommendations": self.unsafe_recommendations,
            "unsafe_recommendation_rate": round(self.unsafe_recommendation_rate, 4),
            "abstentions": self.abstentions,
            "abstention_rate": round(self.abstention_rate, 4),
            "unavailable": self.unavailable,
        }
