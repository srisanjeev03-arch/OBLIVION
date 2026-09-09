"""Path safety, canonicalization, allowed-roots, reparse handling."""
from pathlib import Path
from typing import Protocol


class SafePathValidator(Protocol):
    """Interface for path safety validation."""
    def canonicalize(self, raw_path: str) -> str:
        """Canonicalize and resolve a path to absolute form."""
        ...

    def is_allowed(self, path: str) -> bool:
        """Check if path is within allowed roots."""
        ...

    def reject_reparse(self, path: str) -> bool:
        """Detect and reject reparse points/junctions/symlinks."""
        ...

from .paths import PathSafetyError
from .paths import SafePathValidator as ImplementedSafePathValidator

__all__ = ["ImplementedSafePathValidator", "PathSafetyError", "SafePathValidator"]
