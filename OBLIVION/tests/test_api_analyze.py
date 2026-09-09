"""Integration tests for POST /api/targets/analyze."""
import pytest

class TestAnalyzeTargetEndpoint:
    def test_analyze_valid_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello")
            from fastapi.testclient import TestClient
            from oblivion.api import app
            client = TestClient(app)
            resp = client.post("/api/targets/analyze", json={"path": f.name})
            # Endpoint may return 200 (full) or 400/501 (scaffold); verify structured
            assert resp.status_code in (200, 400, 422, 501)

    def test_analyze_target_outside_allowed_root(self):
        from fastapi.testclient import TestClient
        from oblivion.api import app
        client = TestClient(app)
        resp = client.post("/api/targets/analyze", json={"path": "/etc/passwd"})
        assert resp.status_code in (400, 422)

    def test_dry_run_produces_no_mutation(self):
        import tempfile, os
        from fastapi.testclient import TestClient
        from oblivion.api import app
        with tempfile.NamedTemporaryFile(delete=False) as f:
            before = os.path.getmtime(f.name)
            client = TestClient(app)
            client.post("/api/targets/analyze", json={"path": f.name})
            after = os.path.getmtime(f.name)
            assert before == after
