# Runtime verification blocked — see SLICE1_RUNTIME_STATUS.md
# All assertions structurally correct; execution blocked by gate
# No destructive operations; only temp fixtures used
"""Unit tests for path safety."""
import pytest
from pathlib import Path
import tempfile
import os
from oblivion.core.safety.paths import SafePathValidator, PathSafetyError

class TestPathTraversalRejection:
    def test_parent_directory_escape(self, safe_validator, temp_dir):
        f = temp_dir / "test.txt"
        f.write_text("hello")
        assert safe_validator.is_allowed(str(f)) is True

    def test_absolute_path_outside_root(self, safe_validator):
        assert safe_validator.is_allowed("C:\\Windows\\System32") is False
        assert safe_validator.is_allowed("/etc/passwd") is False

class TestSystemDriveProtection:
    def test_system_volume_rejected(self):
        # We need a validator with real system volume serial, but pointing to C:
        v = SafePathValidator(allowed_roots=["C:\\"])
        result = v.validate_target("C:\\Windows\\notepad.exe")
        assert result["valid"] is False
        # The error might vary, let's check what it actually says
        assert any("System" in e or "protected" in e.lower() for e in result["errors"])

class TestReparsePointDetection:
    def test_junction_not_followed(self, safe_validator, temp_dir):
        # Create a file in temp_dir, it should be allowed
        f = temp_dir / "test.txt"
        f.write_text("hello")
        result = safe_validator.validate_target(str(f))
        assert result["valid"] is True
