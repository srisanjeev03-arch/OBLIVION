import json
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from oblivion.core.discovery.analyzer import TargetAnalyzer

class BaselineManager:
    """Captures and manages the pre-erasure state of a target."""

    def __init__(self, analyzer: Optional[TargetAnalyzer] = None):
        self.analyzer = analyzer or TargetAnalyzer()
        self.baseline: Optional[Dict[str, Any]] = None

    def capture_baseline(self, path: str, scope: str, limitations: Optional[list[str]] = None) -> Dict[str, Any]:
        """
        Capture the pre-erasure state of a target.

        Uses TargetAnalyzer for discovery and hashing.
        """
        analysis = self.analyzer.analyze(path)

        # Map analysis to baseline requirements
        self.baseline = {
            "target_id": analysis["id"],
            "path": analysis["path"],
            "scope": scope,
            "file_inventory": {
                "file_count": analysis["file_count"],
                "total_size": analysis["size"],
                "file_type_distribution": analysis["metadata"].get("file_type_distribution", {})
            },
            "hashes": {
                "sha256": analysis["sha256"]
            },
            "metadata": analysis["metadata"],
            "storage_profile_id": analysis["storage_profile_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "limitations": limitations or []
        }

        return self.baseline

    def to_dict(self) -> Dict[str, Any]:
        """Return the baseline as a dictionary."""
        if not self.baseline:
            raise ValueError("No baseline captured.")
        return self.baseline

    def to_json(self) -> str:
        """Serialize baseline to JSON string."""
        return json.dumps(self.to_dict(), indent=4)

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load baseline from a dictionary."""
        self.baseline = data
