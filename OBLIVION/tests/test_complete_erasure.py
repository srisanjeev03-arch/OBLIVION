import pytest
import tempfile
from pathlib import Path
from oblivion.core.erasure.engine import ErasureEngine, ErasureMode
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.erasure.events import EngineEventEmitter

@pytest.fixture
def engine(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        validator = SafePathValidator(allowed_roots=[tmpdir])
        monkeypatch.setattr(validator, "is_system_volume", lambda path: False)
        emitter = EngineEventEmitter()
        yield ErasureEngine(validator, emitter), Path(tmpdir)

def test_complete_erasure_execution(engine):
    erasure_engine, allowed_root = engine
    file_path = allowed_root / "test_complete.txt"
    file_path.write_text("secure content")

    file_id = erasure_engine.validator._get_file_id(str(file_path))
    result = erasure_engine.execute_complete_erasure(
        "op_complete", str(file_path), erasure_engine.validator.get_volume_serial(str(file_path)), target_file_id=file_id
    )

    assert result["status"] == "COMPLETED"
    assert not file_path.exists()
    assert "COMPLETE_ERASURE" in result["limitations"][0]
