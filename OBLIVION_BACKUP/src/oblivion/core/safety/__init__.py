"""Path safety, canonicalization, allowed-roots, reparse handling."""
from typing import Protocol
from pathlib import Path

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

from .paths import PathSafetyError, SafePathValidator as ImplementedSafePathValidator

__all__ = ["PathSafetyError", "SafePathValidator", "ImplementedSafePathValidator"]
