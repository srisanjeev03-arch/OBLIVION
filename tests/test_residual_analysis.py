import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from oblivion.core.erasure.events import EngineEventEmitter
from oblivion.core.residual.analyzer import ResidualAnalyzer
from oblivion.core.residual.models import ResidualStatus
from oblivion.core.safety.paths import SafePathValidator


@pytest.fixture
def analyzer(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        validator = SafePathValidator(allowed_roots=[str(root)])
        monkeypatch.setattr(validator, "is_system_volume", lambda path: False)
        emitter = MagicMock(spec=EngineEventEmitter)
        yield ResidualAnalyzer(validator, emitter), root

def test_no_residual_detected(analyzer):
    analyzer, root = analyzer
    target_path = root / "absent.txt"
    baseline = {"path": str(target_path)}

    result = analyzer.analyze("op1", baseline)

    assert result["status"] == ResidualStatus.NO_RESIDUAL_DETECTED.name

def test_residual_detected(analyzer):
    analyzer, root = analyzer
    target_path = root / "present.txt"
    target_path.write_text("content")
    baseline = {"path": str(target_path)}

    result = analyzer.analyze("op2", baseline)

    assert result["status"] == ResidualStatus.RESIDUAL_DETECTED.name
    assert any(e["evidence_type"] == "FILE_PRESENT" for e in result["evidence"])
