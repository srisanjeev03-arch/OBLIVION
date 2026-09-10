"""Integration tests for POST /api/targets/analyze."""

class TestAnalyzeTargetEndpoint:
    """Analysis is an authenticated operation.

    These two tests previously built a bare ``TestClient(app)`` with no
    credential and accepted 200/400/422/501 - the contract from before
    authentication was enforced. Production now answers 401, which is correct:
    an unauthenticated caller must not be able to enumerate the filesystem.
    Rather than relax the assertions to accommodate the old contract, they now
    assert the refusal, and authenticated coverage is added alongside so the
    endpoint's real behaviour is still exercised.
    """

    def test_analyze_rejects_unauthenticated_callers(self):
        import tempfile

        from fastapi.testclient import TestClient

        from oblivion.api import app

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello")
            client = TestClient(app)
            resp = client.post("/api/targets/analyze", json={"path": f.name})
            assert resp.status_code == 401

    def test_analyze_outside_allowed_root_rejects_unauthenticated_callers(self):
        from fastapi.testclient import TestClient

        from oblivion.api import app

        client = TestClient(app)
        resp = client.post("/api/targets/analyze", json={"path": "/etc/passwd"})
        # Authentication is checked before path policy, so an anonymous caller
        # cannot learn whether a path exists or is in scope.
        assert resp.status_code == 401

    def test_analyze_valid_file_when_authenticated(self, client, temp_dir):
        f = temp_dir / "analyze_me.txt"
        f.write_text("hello")
        resp = client.post("/api/targets/analyze", json={"path": str(f)})
        assert resp.status_code == 200
        assert resp.json()["canonical_path"]

    def test_analyze_target_outside_allowed_root_when_authenticated(self, client):
        resp = client.post("/api/targets/analyze", json={"path": "/etc/passwd"})
        assert resp.status_code in (400, 422)

    def test_dry_run_produces_no_mutation(self):
        import os
        import tempfile

        from fastapi.testclient import TestClient

        from oblivion.api import app
        with tempfile.NamedTemporaryFile(delete=False) as f:
            before = os.path.getmtime(f.name)
            client = TestClient(app)
            client.post("/api/targets/analyze", json={"path": f.name})
            after = os.path.getmtime(f.name)
            assert before == after
