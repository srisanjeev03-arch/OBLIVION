"""Discovery and analysis (read-only)."""
import hashlib
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from oblivion.core.safety.paths import PathSafetyError, SafePathValidator


class TargetAnalyzer:
    def __init__(self, validator: SafePathValidator | None = None):
        self.validator = validator or SafePathValidator()

    def analyze(self, path: str) -> dict[str, Any]:
        validation = self.validator.validate_target(path)
        if not validation["valid"]:
            raise PathSafetyError("Target invalid: " + "; ".join(validation["errors"]))
        p = Path(path)

        # Compute deterministic target_id: hash of normalized path + file hash
        normalized_path = validation["canonical"].lower().replace("\\", "/")
        sha256_hash = None
        if p.is_file():
            sha256_hash = self._hash_file(p)
            id_input = f"{normalized_path}:{sha256_hash}"
        else:
            id_input = normalized_path
        target_id = hashlib.sha256(id_input.encode("utf-8")).hexdigest()

        # Collect metadata
        metadata = self._collect_metadata(p)

        # Directory enumeration with file-type distribution
        file_count = 0
        total_size = 0
        file_type_distribution: dict[str, int] = {}
        if p.is_dir():
            file_count, total_size, file_type_distribution = self._analyze_directory(p)
        elif p.is_file():
            file_count = 1
            total_size = metadata.get("size_bytes", 0)
            file_type_distribution = self._get_file_type_distribution([p])

        metadata["file_type_distribution"] = file_type_distribution
        metadata["total_size_bytes"] = total_size

        result = {
            "id": target_id,
            "path": str(p.resolve()),
            "type": "directory" if p.is_dir() else "file",
            "size": total_size,
            "file_count": file_count,
            "metadata": metadata,
            "sha256": sha256_hash,
            "storage_profile_id": None,
            "discovered_at": datetime.now(UTC).isoformat(),
            "canonical_path": validation["canonical"],
            "exists": p.exists(),
            "warnings": validation.get("warnings", []),
            "errors": validation.get("errors", []),
        }
        return result

    def _collect_metadata(self, p: Path) -> dict[str, Any]:
        """Collect comprehensive metadata including timestamps, attributes, and file types."""
        metadata: dict[str, Any] = {}
        try:
            stat = p.stat()
            metadata["size_bytes"] = stat.st_size
            metadata["created_at"] = datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat()
            metadata["modified_at"] = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()
            metadata["accessed_at"] = datetime.fromtimestamp(stat.st_atime, tz=UTC).isoformat()

            # Windows file attributes
            if hasattr(os, "stat") and hasattr(stat, "st_file_attributes"):
                metadata["attributes"] = self._decode_windows_attributes(stat.st_file_attributes)

            # File extension/type
            if p.is_file():
                metadata["extension"] = p.suffix.lower() if p.suffix else ""
                metadata["file_type"] = self._classify_file_type(p)

        except Exception as e:
            metadata["collection_error"] = str(e)

        return metadata

    def _decode_windows_attributes(self, attr: int) -> list[str]:
        """Decode Windows file attributes into human-readable flags."""
        flags = []
        FILE_ATTRIBUTE_READONLY = 0x01
        FILE_ATTRIBUTE_HIDDEN = 0x02
        FILE_ATTRIBUTE_SYSTEM = 0x04
        FILE_ATTRIBUTE_DIRECTORY = 0x10
        FILE_ATTRIBUTE_ARCHIVE = 0x20
        FILE_ATTRIBUTE_ENCRYPTED = 0x4000
        FILE_ATTRIBUTE_COMPRESSED = 0x800

        if attr & FILE_ATTRIBUTE_READONLY:
            flags.append("readonly")
        if attr & FILE_ATTRIBUTE_HIDDEN:
            flags.append("hidden")
        if attr & FILE_ATTRIBUTE_SYSTEM:
            flags.append("system")
        if attr & FILE_ATTRIBUTE_DIRECTORY:
            flags.append("directory")
        if attr & FILE_ATTRIBUTE_ARCHIVE:
            flags.append("archive")
        if attr & FILE_ATTRIBUTE_ENCRYPTED:
            flags.append("encrypted")
        if attr & FILE_ATTRIBUTE_COMPRESSED:
            flags.append("compressed")

        return flags

    def _classify_file_type(self, p: Path) -> str:
        """Classify file into broad categories."""
        ext = p.suffix.lower()

        # Document types
        if ext in [".txt", ".doc", ".docx", ".pdf", ".odt", ".rtf"]:
            return "document"
        # Spreadsheet types
        if ext in [".xls", ".xlsx", ".csv", ".ods"]:
            return "spreadsheet"
        # Image types
        if ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff"]:
            return "image"
        # Video types
        if ext in [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"]:
            return "video"
        # Audio types
        if ext in [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"]:
            return "audio"
        # Archive types
        if ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"]:
            return "archive"
        # Code types
        if ext in [".py", ".js", ".java", ".cpp", ".c", ".h", ".cs", ".go", ".rs", ".ts", ".jsx", ".tsx"]:
            return "code"
        # Executable types
        if ext in [".exe", ".dll", ".so", ".dylib", ".msi"]:
            return "executable"
        # Data types
        if ext in [".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".conf"]:
            return "data"

        return "other" if ext else "no_extension"

    def _analyze_directory(self, p: Path) -> tuple[int, int, dict[str, int]]:
        """Recursively enumerate directory and collect file count, total size, and file-type distribution."""
        file_count = 0
        total_size = 0
        distribution: defaultdict[str, int] = defaultdict(int)

        try:
            for root, dirs, files in os.walk(str(p)):
                for file_name in files:
                    file_count += 1
                    file_path = Path(root) / file_name
                    try:
                        total_size += file_path.stat().st_size
                    except Exception:
                        pass

                    file_type = self._classify_file_type(file_path)
                    distribution[file_type] += 1
        except Exception:
            pass

        return file_count, total_size, dict(distribution)

    def _get_file_type_distribution(self, file_paths: list[Path]) -> dict[str, int]:
        """Generate file-type distribution from list of file paths."""
        distribution: defaultdict[str, int] = defaultdict(int)

        for file_path in file_paths:
            file_type = self._classify_file_type(file_path)
            distribution[file_type] += 1

        return dict(distribution)

    def _hash_file(self, p: Path) -> str:
        """Compute SHA-256 hash using streaming pattern."""
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
