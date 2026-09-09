import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock
from oblivion.core.erasure.engine import ErasureEngine, ErasureMode
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.erasure.events import EngineEventEmitter

@pytest.fixture
def engine(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        validator = SafePathValidator(allowed_roots=[tmpdir])
        # Force validator to NOT call out to OS for system volume checks for testing
        monkeypatch.setattr(validator, "is_system_volume", lambda path: False)
        emitter = MagicMock(spec=EngineEventEmitter)
        yield ErasureEngine(validator, emitter), Path(tmpdir), emitter

def test_complete_erasure_safety_validation_fails(engine):
    erasure_engine, allowed_root, emitter = engine
    # Target file outside allowed root
    file_path = Path("C:/Windows/System32/evil.txt")

    # We need to simulate that the validator finds it invalid
    # Since we can't easily change allowed_roots after instantiation,
    # let's just make sure the validation logic is hit.
    # The validator uses is_allowed.

    result = erasure_engine.execute_complete_erasure(
        "op_fail_safety", str(file_path), "SERIAL123"
    )

    assert result["status"] == "FAILED"
    assert "blocked" in result
    assert len(result["blocked"]) > 0
    emitter.emit.assert_any_call("SAFETY_VIOLATION", "op_fail_safety", str(file_path), {"errors": result["blocked"]})

def test_complete_erasure_toctou_failure(engine):
    erasure_engine, allowed_root, emitter = engine
    file_path = allowed_root / "test_toctou.txt"
    file_path.write_text("content")

    # Simulate wrong serial during revalidation
    with pytest.MonkeyPatch.context() as m:
        m.setattr(erasure_engine.validator, "revalidate_handle", lambda *args: False)

        result = erasure_engine.execute_complete_erasure(
            "op_fail_toctou", str(file_path), "WRONG_SERIAL"
        )

        assert result["status"] == "FAILED"
        assert "TOCTOU revalidation failed" in result["blocked"]
        emitter.emit.assert_any_call("SAFETY_VIOLATION", "op_fail_toctou", str(file_path), {"error": "TOCTOU revalidation failed"})

def test_complete_erasure_success_audit_events(engine):
    erasure_engine, allowed_root, emitter = engine
    file_path = allowed_root / "test_success.txt"
    file_path.write_text("secure content")

    file_id = erasure_engine.validator._get_file_id(str(file_path))
    serial = erasure_engine.validator.get_volume_serial(str(file_path))

    result = erasure_engine.execute_complete_erasure(
        "op_success", str(file_path), serial, target_file_id=file_id
    )

    assert result["status"] == "COMPLETED"
    assert not file_path.exists()

    # Verify events
    # We expect: CREATED, ANALYZING, READY, ERASING, VERIFYING, COMPLETED
    emitted_events = [call.args[0] for call in emitter.emit.call_args_list]
    assert "STATE_CHANGE" in emitted_events

    # Check if COMPLETED event was emitted
    completed_events = [call for call in emitter.emit.call_args_list if call.args[0] == "STATE_CHANGE" and call.args[3].get("state") == "COMPLETED"]
    assert len(completed_events) > 0
