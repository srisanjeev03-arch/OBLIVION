"""Run an evaluation dataset against a provider and write a report.

    python scripts/run_evaluation.py                    # baseline, printed
    python scripts/run_evaluation.py --write            # baseline, saved
    python scripts/run_evaluation.py --provider env     # whatever is configured

The default provider is the deterministic baseline, because that is the number
every other result has to be compared against and it runs anywhere - no GPU, no
weights, no network.

``--provider env`` uses whatever ``OBLIVION_AI_PROVIDER`` names. On a machine
with no model configured that produces a report full of UNAVAILABLE, which is
the correct and useful output: it says the model could not be reached, rather
than failing and leaving nothing to look at.

Exit status is 0 whenever the evaluation ran. A FINE_TUNING_RECOMMENDED verdict
is a finding, not a script failure, and making it non-zero would push someone to
suppress it in CI. A non-zero status means the evaluation itself could not run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from oblivion.ai.provider import provider_from_env  # noqa: E402
from oblivion.evaluation import (  # noqa: E402
    BaselineHeuristicProvider,
    DatasetError,
    EvalDataset,
    EvaluationHarness,
)

DEFAULT_DATASET = REPOSITORY_ROOT / "evaluation" / "datasets" / "sensitivity_v1.jsonl"
DEFAULT_REPORT_DIRECTORY = REPOSITORY_ROOT / "evaluation" / "reports"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET),
        help="Path to a JSONL evaluation dataset.",
    )
    parser.add_argument(
        "--provider",
        choices=("baseline", "env"),
        default="baseline",
        help=(
            "baseline: the deterministic heuristic (default, runs anywhere). "
            "env: whatever OBLIVION_AI_PROVIDER names."
        ),
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the JSON report under evaluation/reports/.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Explicit report path. Implies --write.",
    )
    arguments = parser.parse_args()

    try:
        dataset = EvalDataset.from_jsonl(arguments.dataset)
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    provider = (
        BaselineHeuristicProvider()
        if arguments.provider == "baseline"
        else provider_from_env()
    )

    report = EvaluationHarness(provider).run(dataset)
    print(report.summary())

    if arguments.write or arguments.output:
        if arguments.output:
            destination = Path(arguments.output)
        else:
            destination = (
                DEFAULT_REPORT_DIRECTORY
                / f"{dataset.name}-{provider.identity.model_id}.json"
            )
        written = report.write_json(destination)
        print(f"\nwrote {written}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
