import pytest
import tempfile
from pathlib import Path
import os
from oblivion.core.safety.paths import SafePathValidator

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

@pytest.fixture
def safe_validator(temp_dir):
    # Mocking system_volume_serial to avoid C: drive protection
    validator = SafePathValidator(allowed_roots=[str(temp_dir)])
    validator.system_volume_serial = "0x00000000"
    return validator
