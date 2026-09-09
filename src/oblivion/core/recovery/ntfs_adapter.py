import hashlib
import logging
import os
from pathlib import Path

from .adapter import (
    RecoveryAdapter,
    RecoveryConfidence,
    RecoveryItem,
    RecoveryMode,
    RecoveryResult,
)

logger = logging.getLogger(__name__)

class NTFSRecoveryAdapter(RecoveryAdapter):
    """NTFS-specific adapter for forensic recovery (V1).

    V1 capabilities:
    - Filesystem-aware recovery via directory enumeration of the source.
    - Deleted-entry detection is limited to what the current Python environment
      can access without low-level raw-disk access. V1 does NOT pretend to
      recover from unallocated space, MFT, or journal files. Those capabilities
      are reported via the orchestrator (engine.py) as NOT_DETECTED with explicit
      reason metadata.

    Source Immutability:
    - All source files are opened with os.open(..., os.O_RDONLY) so accidental
      writes are not possible. The adapter never uses os.remove, os.unlink,
      Path.unlink, or shutil.rmtree on the source.
    """

    def scan(self, source_path: Path, mode: RecoveryMode) -> list[RecoveryItem]:
        """Performs a read-only scan of the source.

        V1 implementation:
        - Enumerates the source directory and returns a RecoveryItem for each
          existing file with result=RECOVERED and confidence=HIGH (file is
          present and content was read).
        - Files that were deleted via Oblivion's deletion engine will be absent
          and will NOT be reported as recovered. They are reported via the
          orchestrator (engine.py) as NOT_DETECTED.

        Args:
            source_path: The root of the source scope (read-only).
            mode: Recovery mode (FILESYSTEM_AWARE or METADATA_INSPECTION).

        Returns:
            List of RecoveryItem objects found in the source.

        Raises:
            FileNotFoundError: If the source path does not exist.
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")

        items: list[RecoveryItem] = []

        if mode == RecoveryMode.FILESYSTEM_AWARE:
            for root, _dirs, files in os.walk(str(source_path)):
                for name in files:
                    file_path = Path(root) / name
                    try:
                        # Strictly read-only open
                        fd = os.open(str(file_path), os.O_RDONLY)
                        try:
                            content = os.read(fd, 65536)  # read first 64KB for hashing
                        finally:
                            os.close(fd)

                        sha256 = hashlib.sha256(content).hexdigest()
                        stat = os.stat(str(file_path))

                        items.append(RecoveryItem(
                            item_id=f"ntfs-{file_path.name}",
                            original_name=name,
                            size=stat.st_size,
                            relationship="file_present_in_source",
                            source_evidence=f"directory_enumeration:{file_path}",
                            destination=file_path,
                            hash=sha256,
                            confidence=RecoveryConfidence.HIGH,
                            result=RecoveryResult.RECOVERED,
                            metadata={"mode": "FILESYSTEM_AWARE"},
                        ))
                    except Exception as e:
                        # Cannot read file -> INCONCLUSIVE evidence
                        items.append(RecoveryItem(
                            item_id=f"ntfs-{file_path.name}-inconclusive",
                            original_name=name,
                            size=0,
                            relationship="file_present_but_unreadable",
                            source_evidence=f"directory_enumeration:{file_path}",
                            destination=file_path,
                            hash=None,
                            confidence=RecoveryConfidence.INCONCLUSIVE,
                            result=RecoveryResult.INCONCLUSIVE,
                            metadata={"reason": str(e), "mode": "FILESYSTEM_AWARE"},
                        ))
        elif mode == RecoveryMode.METADATA_INSPECTION:
            for root, _dirs, files in os.walk(str(source_path)):
                for name in files:
                    file_path = Path(root) / name
                    try:
                        stat = os.stat(str(file_path))
                        items.append(RecoveryItem(
                            item_id=f"ntfs-meta-{file_path.name}",
                            original_name=name,
                            size=stat.st_size,
                            relationship="metadata_only",
                            source_evidence=f"stat:{file_path}",
                            destination=file_path,
                            hash=None,
                            confidence=RecoveryConfidence.MEDIUM,
                            result=RecoveryResult.PARTIAL,
                            metadata={"mode": "METADATA_INSPECTION"},
                        ))
                    except Exception as e:
                        items.append(RecoveryItem(
                            item_id=f"ntfs-meta-{file_path.name}-failed",
                            original_name=name,
                            size=0,
                            relationship="metadata_unavailable",
                            source_evidence=f"stat_failed:{file_path}",
                            destination=file_path,
                            hash=None,
                            confidence=RecoveryConfidence.INCONCLUSIVE,
                            result=RecoveryResult.FAILED,
                            metadata={"reason": str(e)},
                        ))

        return items
