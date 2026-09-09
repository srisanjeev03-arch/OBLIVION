import logging
from pathlib import Path

from oblivion.core.safety.paths import SafePathValidator

logger = logging.getLogger(__name__)

class RecoveryExporter:
    """Writes recovered items to a validated destination."""

    def __init__(self, validator: SafePathValidator):
        self.validator = validator

    def export(self, item_id: str, content: bytes, destination_path: Path) -> Path:
        """Writes content to destination, ensuring it's safe."""
        # destination_path validation
        validation = self.validator.validate_target(str(destination_path))
        if not validation["valid"]:
            raise ValueError(f"Invalid recovery destination: {validation['errors']}")

        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            with open(destination_path, "wb") as f:
                f.write(content)
            return destination_path
        except Exception as e:
            logger.error(f"Recovery export failed: {e}")
            raise OSError(f"Failed to export recovered item: {e}")
