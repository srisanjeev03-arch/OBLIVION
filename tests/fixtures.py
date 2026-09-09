"""Test fixtures and synthetic data generation."""
import tempfile
from pathlib import Path


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
