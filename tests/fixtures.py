"""Test fixtures and synthetic data generation."""
import tempfile
from pathlib import Path

from oblivion.core.safety.paths import SafePathValidator, encode_file_id


def observed_identity(path: Path | str) -> dict[str, str | None]:
    """The target identity the analyze route records, as ``create_target`` kwargs.

    Fixtures that persist a target directly have to record this the way
    production does. Without it the target carries no identity, and every
    destructive path now refuses - correctly, because an unestablished identity
    is not a matching one. Omitting it here would not be a lighter fixture, it
    would be a fixture describing a target that could never be executed against.

    Neither call depends on the validator's allowed roots; both only read the
    object at ``path``.
    """
    validator = SafePathValidator()
    return {
        "volume_serial": validator.get_volume_serial(str(path)),
        "file_id": encode_file_id(validator._get_file_id(str(path))),
    }


def create_test_target_file() -> Path:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"test data\n")
        return Path(f.name)

def create_test_target_directory() -> Path:
    tmpdir = tempfile.mkdtemp()
    test_dir = Path(tmpdir)
    (test_dir / "file1.txt").write_text("content1")
    (test_dir / "file2.txt").write_text("content2")
    return test_dir
