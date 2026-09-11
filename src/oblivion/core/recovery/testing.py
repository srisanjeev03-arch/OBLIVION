"""Recovery testing: attempting to get the data back, and reporting honestly.

The single rule this module exists to enforce:

    A recovery method that found nothing is evidence about **that method**.
    It is not proof that the data is unrecoverable.

Every result here is therefore scoped to the method that produced it, and the
report carries the methods that were *not* attempted just as prominently as the
ones that were. A caller cannot accidentally read "the filesystem-enumeration
method recovered nothing" as "the data is gone", because no field in this module
makes that second claim and :meth:`RecoveryTestReport.universal_irrecoverability`
returns ``None`` permanently, with a docstring explaining why.

What can actually be attempted from userland, without raw volume access:

* **Filesystem enumeration** - is the content still reachable through the live
  filesystem, under its old name or as a byte-identical copy? A hit here means
  the data is trivially recoverable, which is the most important negative result
  this system can produce.
* **Vault round trip** - for CONTROLLED_RECOVERABLE, the data is *supposed* to be
  recoverable. Confirming the vault object decrypts to the baseline hash proves
  the mode did what it promised.

What cannot, and is declared rather than skipped silently: MFT records, the USN
journal, volume shadow copies, unallocated-space carving, and anything at the
physical layer.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Final

from oblivion.core.assurance.models import (
    RECOVERY_DATA_NOT_RECOVERED,
    RECOVERY_DATA_WAS_RECOVERED,
    RECOVERY_TEST_INCONCLUSIVE,
    AnalysisState,
    RecoveryTestResult,
)

logger = logging.getLogger(__name__)

_HASH_CHUNK: Final = 1024 * 1024


class RecoveryMethod(str, Enum):
    """A specific way of trying to get the data back."""

    FILESYSTEM_ENUMERATION = "filesystem_enumeration"
    VAULT_ROUND_TRIP = "vault_round_trip"
    MFT_RECORD = "mft_record"
    USN_JOURNAL = "usn_journal"
    SHADOW_COPY = "shadow_copy"
    UNALLOCATED_CARVING = "unallocated_carving"
    PHYSICAL_MEDIUM = "physical_medium"


#: Methods this build cannot perform, with the reason. Declared as data so the
#: report can list them; a method that is never attempted must appear in the
#: output, because its silence is otherwise indistinguishable from a clean
#: result.
UNAVAILABLE_METHODS: Final[dict[RecoveryMethod, str]] = {
    RecoveryMethod.MFT_RECORD: (
        "Reading MFT records requires a raw volume handle, which this build does "
        "not acquire."
    ),
    RecoveryMethod.USN_JOURNAL: (
        "Reading the USN change journal requires a raw volume handle, which this "
        "build does not acquire."
    ),
    RecoveryMethod.SHADOW_COPY: (
        "Volume shadow copies are not enumerated or mounted by this build."
    ),
    RecoveryMethod.UNALLOCATED_CARVING: (
        "Carving unallocated space requires a raw volume handle, which this build "
        "does not acquire."
    ),
    RecoveryMethod.PHYSICAL_MEDIUM: (
        "Physical examination of the medium is outside this system's scope and is "
        "never claimed."
    ),
}


@dataclass(frozen=True)
class MethodOutcome:
    """The result of attempting one recovery method.

    ``recovered`` is deliberately tri-state. ``True`` means this method got the
    data back. ``False`` means this method ran and did not - a statement about
    the method, nothing more. ``None`` means the method did not run, and asserts
    nothing whatsoever.
    """

    method: RecoveryMethod
    state: AnalysisState
    recovered: bool | None
    detail: str
    artifacts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state is not AnalysisState.PERFORMED and self.recovered is not None:
            raise ValueError(
                f"{self.method.value} did not run, so it cannot report whether the "
                "data was recovered. A method that was not attempted must assert "
                "nothing."
            )


def _hash_file(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while chunk := handle.read(_HASH_CHUNK):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


@dataclass
class RecoveryTestReport:
    """Every method attempted, every method not attempted, and what each showed."""

    outcomes: tuple[MethodOutcome, ...]

    @property
    def attempted(self) -> list[MethodOutcome]:
        return [o for o in self.outcomes if o.state is AnalysisState.PERFORMED]

    @property
    def not_attempted(self) -> list[MethodOutcome]:
        return [o for o in self.outcomes if o.state is not AnalysisState.PERFORMED]

    @property
    def data_was_recovered(self) -> bool:
        """True when *any* attempted method got the data back.

        One method succeeding is conclusive in the negative direction: the data
        is recoverable, full stop. This asymmetry is the whole point - success
        proves recoverability, failure proves only that one method failed.
        """
        return any(o.recovered is True for o in self.attempted)

    @property
    def universal_irrecoverability(self) -> None:
        """Always ``None``. Nothing in this system can establish this.

        Kept as an explicit, permanently-``None`` property rather than omitted,
        so that a reader looking for the claim finds this docstring instead of
        assuming some other field carries it. Establishing that data cannot be
        recovered by *any* method would require exhausting every method,
        including physical examination of the medium, which this build does not
        and cannot do.
        """
        return None

    @property
    def supported(self) -> list[MethodOutcome]:
        """Methods this build can actually perform.

        The permanently-unavailable methods in :data:`UNAVAILABLE_METHODS` are
        not failures of this run - this build cannot do them at all. Coverage is
        therefore measured against what *is* supported, and the rest are
        reported as limitations rather than counted as gaps this operation could
        have closed.
        """
        return [o for o in self.outcomes if o.method not in UNAVAILABLE_METHODS]

    @property
    def coverage(self) -> AnalysisState:
        """Whether recovery testing ran well enough to support a conclusion.

        ``PERFORMED`` means **every supported method ran** - the same thing the
        residual sweep's ``PERFORMED`` means. Before audit finding M-2 this
        returned ``PERFORMED`` when *any* single method had been attempted,
        which used the same word for "one of several" and "all of them" and let
        a reader overestimate forensic coverage.

        Methods this build cannot perform never appear here; they are
        limitations, and they are listed in every report.
        """
        if not self.outcomes:
            return AnalysisState.NOT_PERFORMED

        states = {o.state for o in self.supported}
        if not states:
            # Nothing supported was even offered - there is no recovery testing
            # capability in play at all.
            return AnalysisState.UNAVAILABLE
        if states == {AnalysisState.PERFORMED}:
            return AnalysisState.PERFORMED
        if AnalysisState.PERFORMED in states or AnalysisState.INCONCLUSIVE in states:
            return AnalysisState.PARTIAL
        return AnalysisState.UNAVAILABLE

    @property
    def method_coverage(self) -> dict[str, list[str]]:
        """Every method, sorted by what actually happened to it.

        Recorded so that evidence preserves *which* methods ran rather than a
        single boolean. "Recovery testing was performed" is not a fact anyone can
        check; "filesystem_enumeration ran and found nothing, five other methods
        were never attempted" is.
        """
        return {
            "supported": [o.method.value for o in self.supported],
            "attempted": [o.method.value for o in self.attempted],
            "successful": [
                o.method.value for o in self.attempted if o.recovered is True
            ],
            "failed": [o.method.value for o in self.attempted if o.recovered is False],
            "unavailable": [o.method.value for o in self.not_attempted],
        }

    def to_assurance_results(self) -> list[RecoveryTestResult]:
        """Translate into what the assurance engine consumes.

        Only attempted methods are translated. A method that did not run has no
        status to contribute, and inventing ``FAILURE`` for it would mean an
        unavailable capability quietly strengthening the assurance verdict.
        """
        results: list[RecoveryTestResult] = []
        for outcome in self.attempted:
            if outcome.recovered is True:
                status = RECOVERY_DATA_WAS_RECOVERED
            elif outcome.recovered is False:
                status = RECOVERY_DATA_NOT_RECOVERED
            else:  # pragma: no cover - forbidden by MethodOutcome.__post_init__
                status = RECOVERY_TEST_INCONCLUSIVE
            results.append(
                RecoveryTestResult(
                    test_id=outcome.method.value,
                    status=status,
                    explanation=outcome.detail,
                )
            )
        return results

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage": self.coverage.name,
            "method_coverage": self.method_coverage,
            "data_was_recovered": self.data_was_recovered,
            "methods": [
                {
                    "method": o.method.value,
                    "state": o.state.name,
                    "recovered": o.recovered,
                    "detail": o.detail,
                    "artifacts": list(o.artifacts),
                }
                for o in self.outcomes
            ],
            "methods_not_attempted": [o.method.value for o in self.not_attempted],
            "scope_note": (
                "Each result describes only the method that produced it. No "
                "combination of these results establishes that the data is "
                "unrecoverable by every method."
            ),
        }


class RecoveryTester:
    """Attempts the recovery methods this build can actually perform."""

    def __init__(self, max_files: int = 5000) -> None:
        self._max_files = max_files

    def run(
        self,
        baseline: dict[str, Any],
        target_path: Path,
        *,
        vault_probe: bool = False,
        vault_recovered_hash: str | None = None,
    ) -> RecoveryTestReport:
        """Run every available method and report each separately."""
        outcomes: list[MethodOutcome] = [
            self._filesystem_enumeration(baseline, target_path)
        ]

        if vault_probe:
            outcomes.append(self._vault_round_trip(baseline, vault_recovered_hash))

        for method, reason in UNAVAILABLE_METHODS.items():
            outcomes.append(
                MethodOutcome(
                    method=method,
                    state=AnalysisState.UNAVAILABLE,
                    recovered=None,
                    detail=reason,
                )
            )

        return RecoveryTestReport(tuple(outcomes))

    def _filesystem_enumeration(
        self, baseline: dict[str, Any], target_path: Path
    ) -> MethodOutcome:
        """Is the content still reachable through the live filesystem?

        Two ways it can be: the target itself survived, or a byte-identical copy
        exists in scope. Either means the data is recoverable without any
        forensic technique at all.
        """
        scope = target_path.parent
        expected = (baseline.get("hashes") or {}).get("sha256")

        if not scope.is_dir():
            return MethodOutcome(
                RecoveryMethod.FILESYSTEM_ENUMERATION,
                AnalysisState.UNAVAILABLE,
                None,
                f"Scan scope {scope} is not a readable directory.",
            )

        if target_path.exists():
            return MethodOutcome(
                RecoveryMethod.FILESYSTEM_ENUMERATION,
                AnalysisState.PERFORMED,
                True,
                (
                    f"The target is still present at {target_path} and can be read "
                    "directly. No forensic technique was required."
                ),
                (str(target_path),),
            )

        if not expected:
            return MethodOutcome(
                RecoveryMethod.FILESYSTEM_ENUMERATION,
                AnalysisState.UNAVAILABLE,
                None,
                (
                    "The baseline records no SHA-256, so a surviving copy could not "
                    "be identified by content."
                ),
            )

        examined = 0
        for root, _dirs, files in os.walk(scope, followlinks=False):
            for filename in files:
                if examined >= self._max_files:
                    return MethodOutcome(
                        RecoveryMethod.FILESYSTEM_ENUMERATION,
                        AnalysisState.INCONCLUSIVE,
                        None,
                        (
                            f"Search stopped after {self._max_files} files; the scope "
                            "was not searched exhaustively."
                        ),
                    )
                candidate = Path(root) / filename
                examined += 1
                if _hash_file(candidate) == expected:
                    return MethodOutcome(
                        RecoveryMethod.FILESYSTEM_ENUMERATION,
                        AnalysisState.PERFORMED,
                        True,
                        (
                            f"A byte-identical copy of the target content was found "
                            f"at {candidate}. The content is recoverable."
                        ),
                        (str(candidate),),
                    )

        return MethodOutcome(
            RecoveryMethod.FILESYSTEM_ENUMERATION,
            AnalysisState.PERFORMED,
            False,
            (
                f"Live filesystem enumeration over {examined} file(s) in {scope} did "
                "not reach the target content. This describes filesystem "
                "enumeration only; no forensic recovery method was attempted."
            ),
        )

    def _vault_round_trip(
        self, baseline: dict[str, Any], recovered_hash: str | None
    ) -> MethodOutcome:
        """For CONTROLLED_RECOVERABLE, recovery succeeding is the correct outcome.

        The mode's entire promise is that an authorized actor can get the data
        back, so a successful round trip confirms the mode worked - it is not a
        failure of erasure.
        """
        expected = (baseline.get("hashes") or {}).get("sha256")
        if recovered_hash is None:
            return MethodOutcome(
                RecoveryMethod.VAULT_ROUND_TRIP,
                AnalysisState.UNAVAILABLE,
                None,
                "No vault object was read back, so the round trip was not tested.",
            )
        if not expected:
            return MethodOutcome(
                RecoveryMethod.VAULT_ROUND_TRIP,
                AnalysisState.UNAVAILABLE,
                None,
                "The baseline records no SHA-256 to compare the restored content to.",
            )
        if recovered_hash == expected:
            return MethodOutcome(
                RecoveryMethod.VAULT_ROUND_TRIP,
                AnalysisState.PERFORMED,
                True,
                (
                    "The vault object decrypted to content matching the baseline "
                    "hash. CONTROLLED_RECOVERABLE is designed to be recoverable by "
                    "an authorized actor, so this confirms the mode behaved as "
                    "promised."
                ),
            )
        return MethodOutcome(
            RecoveryMethod.VAULT_ROUND_TRIP,
            AnalysisState.PERFORMED,
            False,
            (
                "The vault object did not decrypt to the baseline hash, so the "
                "recovery promise of this mode is not satisfied."
            ),
        )
