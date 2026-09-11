"""Model evaluation: measure first, then decide about fine-tuning.

Deterministic and dependency-free. The same dataset and provider produce the
same report on any machine, which is what makes the fine-tuning decision
something a reader can check rather than take on trust.

See ``docs/OBLIVION_DOCUMENTATION.md §26``.
"""

from oblivion.evaluation.baseline import RULES, BaselineHeuristicProvider
from oblivion.evaluation.dataset import (
    DATASET_DIRECTORY,
    DatasetError,
    EvalCase,
    EvalDataset,
)
from oblivion.evaluation.harness import (
    DECISION_THRESHOLDS,
    FINE_TUNING_NOT_REQUIRED,
    FINE_TUNING_RECOMMENDED,
    CaseOutcome,
    EvaluationHarness,
    EvaluationReport,
)
from oblivion.evaluation.metrics import (
    CalibrationMetrics,
    ClassificationMetrics,
    ClassMetrics,
    SafetyMetrics,
)

__all__ = [
    "DATASET_DIRECTORY",
    "DECISION_THRESHOLDS",
    "FINE_TUNING_NOT_REQUIRED",
    "FINE_TUNING_RECOMMENDED",
    "RULES",
    "BaselineHeuristicProvider",
    "CalibrationMetrics",
    "CaseOutcome",
    "ClassMetrics",
    "ClassificationMetrics",
    "DatasetError",
    "EvalCase",
    "EvalDataset",
    "EvaluationHarness",
    "EvaluationReport",
    "SafetyMetrics",
]
