import hashlib
import json
import io
from pathlib import Path
from typing import Optional, Any, Union

class Hasher:
    """Provides deterministic hashing services for the Oblivion platform."""

    CHUNK_SIZE = 65536

    @staticmethod
    def hash_file(file_path: Path) -> str:
        """
        Compute SHA-256 hash of a file using streaming pattern.

        Args:
            file_path: Path to the file to hash.

        Returns:
            SHA-256 hex digest.

        Raises:
            IOError: If the file cannot be opened or read.
            ValueError: If the path is not a file or does not exist.
        """
        if not file_path.exists():
            raise ValueError(f"Path does not exist: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(Hasher.CHUNK_SIZE)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except IOError as e:
            # Re-raise with context to be handled by higher level
            raise IOError(f"Failed to hash file {file_path}: {e}") from e

    @staticmethod
    def hash_data(data: Union[str, bytes, dict[str, Any]]) -> str:
        """
        Compute SHA-256 hash of structured data.

        For dicts, ensures deterministic serialization.
        """
        hasher = hashlib.sha256()
        if isinstance(data, dict):
            # Sort keys for deterministic output
            serialized = json.dumps(data, sort_keys=True).encode("utf-8")
            hasher.update(serialized)
        elif isinstance(data, str):
            hasher.update(data.encode("utf-8"))
        else:
            hasher.update(data)
        return hasher.hexdigest()
