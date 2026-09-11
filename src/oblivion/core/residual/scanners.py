"""Residual scanners that look for things, rather than only checking a path.

Path existence answers one question: is the target still at its path? That is
necessary and nowhere near sufficient. A logical deletion leaves several other
observable traces, and the ones reachable from userland on NTFS - without raw
volume access - are worth actually looking for:

* **A surviving copy of the same content.** The baseline records the target's
  SHA-256. If a byte-identical file exists elsewhere in scope, the *content* was
  not erased even though the named file was. This is the highest-value check
  here, and it is a real search rather than an inference.
* **Name remnants.** Editors, backup tools and sync clients leave ``file.txt~``,
  ``file.txt.bak``, ``~$file.txt`` and similar beside the original.
* **Alternate data streams.** NTFS can hold content in a named stream that a
  directory listing never shows.

Every scanner reports whether it actually ran, using the assurance module's
:class:`AnalysisState`. This matters more than what any of them found: a scanner
that could not run must never contribute to a claim that nothing was found. The
two axes - *what was found* and *whether anyone looked* - stay separate here
exactly as they do in the evidence and assurance models.

What is deliberately **not** claimed: nothing here inspects the MFT, the USN
journal, volume shadow copies, unallocated space or the physical medium. Those
need raw volume access, which the privileged service reports as UNAVAILABLE.
Their absence is reported as a limitation, never as a clean result.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from oblivion.core.assurance.models import AnalysisState

from .models import EvidenceConfidence, EvidenceType, ResidualEvidence

logger = logging.getLogger(__name__)

#: Read size for hashing. Large enough to be efficient, small enough that a
#: scanner never holds a whole file in memory - the brief forbids loading drives
#: into memory, and the same reasoning applies at file scale.
_HASH_CHUNK: Final = 1024 * 1024

#: Upper bound on how many files one scan will hash. A residual scan runs inside
#: an operation, and an unbounded walk of a large scope would turn a security
#: check into a denial of service against the operation itself.
DEFAULT_MAX_FILES_SCANNED: Final = 5000

#: Suffix and prefix patterns that editors, backup tools and sync clients leave
#: beside a file. Matching is on the *stem*, so `report.txt` matches
#: `report.txt.bak`, `report.txt~` and `~$report.txt`.
_REMNANT_SUFFIXES: Final = (".bak", ".tmp", ".old", ".orig", ".swp", "~")
_REMNANT_PREFIXES: Final = ("~$", "~", ".#")

#: Capabilities this build cannot provide, reported so their absence is never
#: mistaken for a clean result.
UNAVAILABLE_CAPABILITIES: Final[tuple[str, ...]] = (
    "MFT record inspection (requires raw volume access, which is not performed)",
    "USN journal inspection (requires raw volume access, which is not performed)",
    "Volume shadow copy inspection (not performed)",
    "Unallocated-space carving (requires raw volume access, which is not performed)",
    "Physical medium examination (not performed and not claimed)",
)


@dataclass(frozen=True)
class ScanOutcome:
    """What one scanner did, and whether it managed to do it.

    ``state`` is the important field. ``PERFORMED`` means the scanner ran and its
    findings can be relied upon; ``UNAVAILABLE`` means it could not run here and
    its empty findings prove nothing at all.
    """

    scanner: str
    state: AnalysisState
    evidence: tuple[ResidualEvidence, ...] = ()
    limitation: str | None = None
    files_examined: int = 0

    @property
    def usable(self) -> bool:
        return self.state is AnalysisState.PERFORMED


class ResidualScanner(ABC):
    """A scanner that looks for one kind of residual trace."""

    name: str = "scanner"

    @abstractmethod
    def scan(self, baseline: dict[str, Any], target_path: Path) -> ScanOutcome:
        """Look, and report both findings and whether looking succeeded."""


def _hash_file(path: Path) -> str | None:
    """SHA-256 of a file, or None if it could not be read.

    None is a real answer - "could not read" - and callers must not treat it as
    "did not match".
    """
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while chunk := handle.read(_HASH_CHUNK):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _scan_scope(target_path: Path) -> Path:
    """The directory a residual scan searches.

    The target's parent: close enough to find copies left beside the original,
    bounded enough not to walk a volume. Widening this is a policy decision, not
    a default.
    """
    return target_path.parent


class PathExistenceScanner(ResidualScanner):
    """Is the target still at its path?

    The original check, kept because it is the most direct evidence there is.
    Uses ``lexists`` so a dangling symlink counts as an entry that survived.
    """

    name = "path_existence"

    # `baseline` is part of the ResidualScanner interface. Scanners that do not
    # consult it still declare it, so the suite can call every scanner the same
    # way and adding one never means touching the dispatch.
    def scan(
        self,
        baseline: dict[str, Any],  # noqa: ARG002 - scanner interface
        target_path: Path,
    ) -> ScanOutcome:
        try:
            present = os.path.lexists(target_path)
        except OSError as exc:
            return ScanOutcome(
                self.name,
                AnalysisState.UNAVAILABLE,
                limitation=f"Target path could not be read: {exc}",
            )

        if not present:
            return ScanOutcome(
                self.name,
                AnalysisState.PERFORMED,
                (
                    ResidualEvidence(
                        evidence_type=EvidenceType.FILE_ABSENT,
                        confidence=EvidenceConfidence.HIGH,
                        explanation=f"Target {target_path} is absent from its path.",
                        artifact_path=str(target_path),
                        metadata={},
                    ),
                ),
            )

        is_directory = target_path.is_dir()
        return ScanOutcome(
            self.name,
            AnalysisState.PERFORMED,
            (
                ResidualEvidence(
                    evidence_type=(
                        EvidenceType.DIRECTORY_REMAINS
                        if is_directory
                        else EvidenceType.FILE_PRESENT
                    ),
                    confidence=EvidenceConfidence.HIGH,
                    explanation=f"Target {target_path} still exists.",
                    artifact_path=str(target_path),
                    metadata={},
                ),
            ),
        )


class CopyByHashScanner(ResidualScanner):
    """Search the scope for a file whose content matches the baseline hash.

    The most consequential check here. Erasing a named file does not erase its
    content if a byte-identical copy sits beside it, and no amount of path
    checking would reveal that. A match is reported at HIGH confidence because
    a SHA-256 collision is not the explanation.

    Without a baseline hash there is nothing to compare against, and the scanner
    reports UNAVAILABLE rather than silently finding nothing.
    """

    name = "content_copy_by_hash"

    def __init__(self, max_files: int = DEFAULT_MAX_FILES_SCANNED) -> None:
        self._max_files = max_files

    def scan(self, baseline: dict[str, Any], target_path: Path) -> ScanOutcome:
        expected = (baseline.get("hashes") or {}).get("sha256")
        if not expected:
            return ScanOutcome(
                self.name,
                AnalysisState.UNAVAILABLE,
                limitation=(
                    "The baseline records no SHA-256 for the target, so surviving "
                    "copies of its content cannot be searched for."
                ),
            )

        scope = _scan_scope(target_path)
        if not scope.is_dir():
            return ScanOutcome(
                self.name,
                AnalysisState.UNAVAILABLE,
                limitation=f"Scan scope {scope} is not a readable directory.",
            )

        findings: list[ResidualEvidence] = []
        examined = 0
        truncated = False

        for root, _dirs, files in os.walk(scope, followlinks=False):
            for filename in files:
                if examined >= self._max_files:
                    truncated = True
                    break
                candidate = Path(root) / filename
                if candidate == target_path:
                    continue
                examined += 1
                digest = _hash_file(candidate)
                if digest is None:
                    findings.append(
                        ResidualEvidence(
                            evidence_type=EvidenceType.UNREADABLE,
                            confidence=EvidenceConfidence.INCONCLUSIVE,
                            explanation=(
                                f"{candidate} could not be read, so it could not be "
                                "ruled out as a surviving copy."
                            ),
                            artifact_path=str(candidate),
                            metadata={},
                        )
                    )
                    continue
                if digest == expected:
                    findings.append(
                        ResidualEvidence(
                            evidence_type=EvidenceType.HASH_MATCH,
                            confidence=EvidenceConfidence.HIGH,
                            explanation=(
                                f"{candidate} is byte-identical to the erased target. "
                                "The content survives even though the named file "
                                "was removed."
                            ),
                            artifact_path=str(candidate),
                            metadata={"sha256": digest},
                        )
                    )
            if truncated:
                break

        if truncated:
            # A truncated search cannot support "nothing was found", so the whole
            # scan degrades rather than reporting a partial sweep as complete.
            return ScanOutcome(
                self.name,
                AnalysisState.INCONCLUSIVE,
                tuple(findings),
                limitation=(
                    f"Scan stopped after {self._max_files} files; the scope was not "
                    "searched exhaustively, so the absence of a copy is not "
                    "established."
                ),
                files_examined=examined,
            )

        return ScanOutcome(
            self.name, AnalysisState.PERFORMED, tuple(findings), files_examined=examined
        )


class NameRemnantScanner(ResidualScanner):
    """Look for backup, temporary and versioned siblings of the target's name.

    These are produced by ordinary software - editors, sync clients, Office - and
    routinely survive a deletion of the file they shadow. They are reported at
    MEDIUM confidence: the name is suggestive, and only reading the content would
    make it certain.
    """

    name = "name_remnants"

    def scan(
        self,
        baseline: dict[str, Any],  # noqa: ARG002 - scanner interface
        target_path: Path,
    ) -> ScanOutcome:
        scope = _scan_scope(target_path)
        if not scope.is_dir():
            return ScanOutcome(
                self.name,
                AnalysisState.UNAVAILABLE,
                limitation=f"Scan scope {scope} is not a readable directory.",
            )

        stem = target_path.name
        findings: list[ResidualEvidence] = []

        try:
            entries = list(os.scandir(scope))
        except OSError as exc:
            return ScanOutcome(
                self.name,
                AnalysisState.UNAVAILABLE,
                limitation=f"Scan scope could not be listed: {exc}",
            )

        for entry in entries:
            name = entry.name
            if name == stem:
                continue
            if not self._looks_like_remnant(name, stem):
                continue
            findings.append(
                ResidualEvidence(
                    evidence_type=EvidenceType.METADATA_REMAINS,
                    confidence=EvidenceConfidence.MEDIUM,
                    explanation=(
                        f"{name} appears to be a backup, temporary or versioned "
                        f"remnant of {stem} and still exists."
                    ),
                    artifact_path=entry.path,
                    metadata={"related_to": stem},
                )
            )

        return ScanOutcome(
            self.name,
            AnalysisState.PERFORMED,
            tuple(findings),
            files_examined=len(entries),
        )

    @staticmethod
    def _looks_like_remnant(name: str, stem: str) -> bool:
        lowered = name.lower()
        target = stem.lower()
        if lowered.startswith(target) and any(
            lowered.endswith(suffix) for suffix in _REMNANT_SUFFIXES
        ):
            return True
        return any(
            lowered in (f"{prefix}{target}", f"{prefix}{target}{suffix}")
            for prefix in _REMNANT_PREFIXES
            for suffix in ("", *_REMNANT_SUFFIXES)
        )


class AlternateDataStreamScanner(ResidualScanner):
    """Enumerate NTFS alternate data streams on entries in the scan scope.

    A named stream can hold a full copy of a file's content while a directory
    listing shows nothing unusual, which makes it a genuine hiding place for
    data that a deletion was meant to remove.

    Non-Windows hosts and filesystems without stream support report UNAVAILABLE.
    That is the honest answer: the check did not happen, so its silence means
    nothing.
    """

    name = "alternate_data_streams"

    def scan(
        self,
        baseline: dict[str, Any],  # noqa: ARG002 - scanner interface
        target_path: Path,
    ) -> ScanOutcome:
        if sys.platform != "win32":
            return ScanOutcome(
                self.name,
                AnalysisState.UNAVAILABLE,
                limitation=(
                    "Alternate data streams are an NTFS feature; this host is not "
                    "Windows, so no stream enumeration was performed."
                ),
            )

        scope = _scan_scope(target_path)
        if not scope.is_dir():
            return ScanOutcome(
                self.name,
                AnalysisState.UNAVAILABLE,
                limitation=f"Scan scope {scope} is not a readable directory.",
            )

        try:
            entries = [e for e in os.scandir(scope) if e.is_file(follow_symlinks=False)]
        except OSError as exc:
            return ScanOutcome(
                self.name,
                AnalysisState.UNAVAILABLE,
                limitation=f"Scan scope could not be listed: {exc}",
            )

        findings: list[ResidualEvidence] = []
        for entry in entries:
            for stream_name, stream_size in _enumerate_streams(entry.path):
                findings.append(
                    ResidualEvidence(
                        evidence_type=EvidenceType.METADATA_REMAINS,
                        confidence=EvidenceConfidence.MEDIUM,
                        explanation=(
                            f"{entry.name} carries alternate data stream "
                            f"{stream_name} of {stream_size} bytes, which a "
                            "directory listing does not show."
                        ),
                        artifact_path=f"{entry.path}{stream_name}",
                        metadata={"stream": stream_name, "size": stream_size},
                    )
                )

        return ScanOutcome(
            self.name,
            AnalysisState.PERFORMED,
            tuple(findings),
            files_examined=len(entries),
        )


def _enumerate_streams(path: str) -> list[tuple[str, int]]:
    """Named alternate data streams on one file, excluding the default ``::$DATA``.

    Returns an empty list on any failure. A scanner-level UNAVAILABLE is the
    right signal for "streams could not be examined at all"; a single unreadable
    file should not invalidate a whole scan.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32

    class Win32FindStreamData(ctypes.Structure):
        _fields_ = [
            ("StreamSize", ctypes.c_longlong),
            ("cStreamName", ctypes.c_wchar * 296),
        ]

    kernel32.FindFirstStreamW.restype = wintypes.HANDLE
    kernel32.FindFirstStreamW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.FindNextStreamW.restype = wintypes.BOOL
    kernel32.FindNextStreamW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel32.FindClose.restype = wintypes.BOOL
    kernel32.FindClose.argtypes = [wintypes.HANDLE]

    invalid = ctypes.c_void_p(-1).value
    data = Win32FindStreamData()
    handle = kernel32.FindFirstStreamW(path, 0, ctypes.byref(data), 0)
    if handle == invalid or not handle:
        return []

    streams: list[tuple[str, int]] = []
    try:
        while True:
            name = data.cStreamName
            if name and name != "::$DATA":
                streams.append((name, int(data.StreamSize)))
            if not kernel32.FindNextStreamW(handle, ctypes.byref(data)):
                break
    finally:
        kernel32.FindClose(handle)
    return streams


@dataclass
class ResidualScanReport:
    """The combined result of every scanner, with coverage kept separate.

    ``positive_findings`` describes *what was found*. ``coverage`` describes
    *whether anyone was able to look*. Collapsing them would let an environment
    where nothing could run produce the same report as one where everything ran
    and found nothing, which is the exact confusion this system exists to
    prevent.
    """

    outcomes: tuple[ScanOutcome, ...]
    limitations: tuple[str, ...] = ()

    @property
    def evidence(self) -> list[ResidualEvidence]:
        return [e for outcome in self.outcomes for e in outcome.evidence]

    @property
    def positive_findings(self) -> list[ResidualEvidence]:
        """Evidence that something survived, as opposed to evidence of absence."""
        return [
            e
            for e in self.evidence
            if e.evidence_type
            in (
                EvidenceType.FILE_PRESENT,
                EvidenceType.DIRECTORY_REMAINS,
                EvidenceType.HASH_MATCH,
                EvidenceType.METADATA_REMAINS,
                EvidenceType.RECOVERY_CANDIDATE,
            )
        ]

    @property
    def coverage(self) -> AnalysisState:
        """Whether the scan as a whole can support a conclusion.

        ``PERFORMED`` only when every scanner ran. One scanner that could not run
        makes the sweep incomplete, and an incomplete sweep cannot support
        "nothing is there".

        A sweep where some scanners ran is ``PARTIAL`` rather than
        ``INCONCLUSIVE``: real evidence was gathered, just not all of it. That
        distinction is what lets assurance say "partial" instead of either
        overclaiming or discarding a genuine result - audit finding M-2.
        """
        if not self.outcomes:
            return AnalysisState.NOT_PERFORMED
        states = {outcome.state for outcome in self.outcomes}
        if states == {AnalysisState.PERFORMED}:
            return AnalysisState.PERFORMED
        if AnalysisState.PERFORMED in states or AnalysisState.INCONCLUSIVE in states:
            return AnalysisState.PARTIAL
        return AnalysisState.UNAVAILABLE

    @property
    def scanner_coverage(self) -> dict[str, list[str]]:
        """Which scanners ran and which did not, by name.

        Preserved so a reader never has to infer coverage from the number of
        findings. An empty findings list means nothing without this.
        """
        return {
            "supported": [o.scanner for o in self.outcomes],
            "ran": [
                o.scanner for o in self.outcomes if o.state is AnalysisState.PERFORMED
            ],
            "inconclusive": [
                o.scanner
                for o in self.outcomes
                if o.state is AnalysisState.INCONCLUSIVE
            ],
            "unavailable": [
                o.scanner for o in self.outcomes if o.state is AnalysisState.UNAVAILABLE
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage": self.coverage.name,
            "scanner_coverage": self.scanner_coverage,
            "scanners": [
                {
                    "scanner": o.scanner,
                    "state": o.state.name,
                    "findings": len(o.evidence),
                    "files_examined": o.files_examined,
                    "limitation": o.limitation,
                }
                for o in self.outcomes
            ],
            "evidence": [
                {
                    "evidence_type": e.evidence_type.name,
                    "confidence": e.confidence.name,
                    "explanation": e.explanation,
                    "artifact_path": e.artifact_path,
                }
                for e in self.evidence
            ],
            "limitations": list(self.limitations),
        }


@dataclass
class ResidualScanSuite:
    """Runs every scanner and reports findings and coverage separately."""

    scanners: list[ResidualScanner] = field(default_factory=list)

    @classmethod
    def default(cls) -> ResidualScanSuite:
        return cls(
            scanners=[
                PathExistenceScanner(),
                CopyByHashScanner(),
                NameRemnantScanner(),
                AlternateDataStreamScanner(),
            ]
        )

    def run(self, baseline: dict[str, Any], target_path: Path) -> ResidualScanReport:
        outcomes: list[ScanOutcome] = []
        limitations: list[str] = list(UNAVAILABLE_CAPABILITIES)

        for scanner in self.scanners:
            try:
                outcome = scanner.scan(baseline, target_path)
            except Exception as exc:  # noqa: BLE001 - one scanner must not end the scan
                logger.exception("residual.scanner.failed scanner=%s", scanner.name)
                outcome = ScanOutcome(
                    scanner.name,
                    AnalysisState.UNAVAILABLE,
                    limitation=(
                        f"Scanner raised {type(exc).__name__} and produced no result"
                    ),
                )
            outcomes.append(outcome)
            if outcome.limitation:
                limitations.append(f"{outcome.scanner}: {outcome.limitation}")

        return ResidualScanReport(tuple(outcomes), tuple(limitations))
