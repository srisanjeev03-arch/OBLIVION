from oblivion.core.baseline.manager import BaselineManager
from oblivion.core.discovery import TargetAnalyzer


def test_baseline_capture(safe_validator, temp_dir):
    f = temp_dir / "baseline_test.txt"
    f.write_text("data")

    analyzer = TargetAnalyzer(validator=safe_validator)
    manager = BaselineManager(analyzer=analyzer)

    baseline = manager.capture_baseline(str(f), "SELECTIVE_PERMANENT")

    assert "target_id" in baseline
    assert baseline["path"] == str(f.resolve())
    assert baseline["scope"] == "SELECTIVE_PERMANENT"
    assert "sha256" in baseline["hashes"]

def test_baseline_serialization(safe_validator, temp_dir):
    f = temp_dir / "json_test.txt"
    f.write_text("data")

    analyzer = TargetAnalyzer(validator=safe_validator)
    manager = BaselineManager(analyzer=analyzer)
    manager.capture_baseline(str(f), "COMPLETE_ERASURE")

    json_data = manager.to_json()
    assert "target_id" in json_data
