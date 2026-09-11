"""The audit HTTP surface: who may read it, and what reading it records.

The permission model is the point of these tests. `audit.view` and
`audit.verify` are granted to ADMIN and AUDITOR only, so an OPERATOR holding
the authority to *erase* still cannot read or verify the record of having done
so. That asymmetry is deliberate, and it is what makes the log evidence rather
than a convenience.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from oblivion.api import app


def _events(client: TestClient, **params) -> dict:
    response = client.get("/api/audit/events", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Authentication and authorization are different answers
# ---------------------------------------------------------------------------


def test_unauthenticated_access_is_401_not_403():
    """401 says "identify yourself"; 403 says "you are known and refused"."""
    anonymous = TestClient(app)
    for method, path in (("get", "/api/audit/events"), ("post", "/api/audit/verify")):
        response = getattr(anonymous, method)(path)
        assert response.status_code == 401, f"{path}: {response.status_code}"
        assert response.json()["error_code"] in {"UNAUTHENTICATED", "SESSION_INVALID"}


def test_an_authenticated_principal_without_the_permission_is_403(viewer_client):
    """A VIEWER is a real principal, so the refusal must be 403, never 401."""
    response = viewer_client.get("/api/audit/events")
    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN"


def test_an_operator_cannot_read_the_log_of_its_own_actions(operator_client):
    """Holding the authority to erase does not confer the authority to audit."""
    assert operator_client.get("/api/audit/events").status_code == 403
    assert operator_client.post("/api/audit/verify").status_code == 403


def test_an_investigator_cannot_read_the_audit_log(investigator_client):
    assert investigator_client.get("/api/audit/events").status_code == 403


@pytest.mark.parametrize("fixture_name", ["admin_client", "auditor_client"])
def test_admin_and_auditor_may_read_and_verify(fixture_name, request):
    client = request.getfixturevalue(fixture_name)
    assert client.get("/api/audit/events").status_code == 200
    assert client.post("/api/audit/verify").status_code == 200


# ---------------------------------------------------------------------------
# Reading the log is itself recorded
# ---------------------------------------------------------------------------


def test_querying_the_audit_log_records_the_query(admin_client):
    """A log that cannot answer "who read this" is missing the insider's trail."""
    before = _events(admin_client)["total_records"]
    after = _events(admin_client)["total_records"]
    assert after > before

    page = _events(admin_client, event_type="AUDIT_LOG_QUERIED")
    assert page["returned"] >= 1
    entry = page["events"][-1]
    assert entry["event_type"] == "AUDIT_LOG_QUERIED"
    assert entry["actor_source"] == "AUTHENTICATED_SESSION"
    assert entry["actor_id"]


def test_verifying_the_audit_log_records_the_verification(admin_client):
    admin_client.post("/api/audit/verify")
    page = _events(admin_client, event_type="AUDIT_LOG_VERIFIED")
    assert page["returned"] >= 1
    assert page["events"][-1]["actor_source"] == "AUTHENTICATED_SESSION"


# ---------------------------------------------------------------------------
# The published record carries what an independent verifier needs
# ---------------------------------------------------------------------------


def test_published_events_expose_the_chain_fields(admin_client):
    page = _events(admin_client, limit=10)
    assert page["events"], "the log should not be empty after authenticating"
    for entry in page["events"]:
        assert len(entry["digest"]) == 64
        assert entry["sequence"] >= 1
        # A client can re-link the chain itself rather than trusting the verdict.
        if entry["sequence"] > 1:
            assert entry["previous_audit_id"]
            assert entry["previous_audit_digest"]


def test_the_chain_published_to_a_client_actually_links(admin_client):
    """Re-link the page client-side: each record must name the one before it."""
    events = _events(admin_client, limit=100)["events"]
    for earlier, later in zip(events, events[1:], strict=False):
        assert later["previous_audit_id"] == earlier["audit_id"]
        assert later["previous_audit_digest"] == earlier["digest"]
        assert later["sequence"] == earlier["sequence"] + 1


# ---------------------------------------------------------------------------
# Verification is the server's answer, not the caller's
# ---------------------------------------------------------------------------


def test_verification_reports_scope_limits_alongside_the_verdict(admin_client):
    body = admin_client.post("/api/audit/verify").json()
    assert body["status"] in {"INTACT", "BROKEN", "UNVERIFIABLE"}
    joined = " ".join(body["does_not_prove"]).lower()
    assert "erasure" in joined
    assert "evidence integrity" in joined
    assert "audit log only" in body["scope_note"].lower()


def test_a_client_cannot_assert_the_chain_is_intact(admin_client):
    """Injected verdict fields must be rejected or ignored, never believed."""
    injected = {
        "status": "INTACT",
        "checked": 9999,
        "proves": ["everything is fine"],
        "links": [],
        "reason": "trust me",
    }
    response = admin_client.post("/api/audit/verify", json=injected)
    # Either the body is refused outright, or the extra fields are discarded and
    # the server answers for itself. What must never happen is the client's
    # claim being echoed back as the verdict.
    if response.status_code == 200:
        body = response.json()
        assert body["reason"] != "trust me"
        assert body["checked"] != 9999
    else:
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Filters fail loudly rather than silently widening the answer
# ---------------------------------------------------------------------------


def test_an_unknown_event_type_filter_is_rejected(admin_client):
    response = admin_client.get("/api/audit/events", params={"event_type": "NOT_A_TYPE"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "UNKNOWN_EVENT_TYPE"


def test_an_unknown_outcome_filter_is_rejected(admin_client):
    response = admin_client.get("/api/audit/events", params={"outcome": "OK"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "UNKNOWN_OUTCOME"


def test_the_page_size_is_bounded(admin_client):
    assert admin_client.get("/api/audit/events", params={"limit": 100000}).status_code == 422


# ---------------------------------------------------------------------------
# No write verb exists on the audit surface
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_no_write_verb_is_routed_on_the_audit_surface(method, admin_client):
    response = getattr(admin_client, method)("/api/audit/events")
    assert response.status_code in {404, 405}


# ---------------------------------------------------------------------------
# Authentication events reach the log
# ---------------------------------------------------------------------------


def test_a_failed_login_is_recorded_without_the_password(admin_client):
    """The attempt survives its own rolled-back 401, and carries no credential."""
    anonymous = TestClient(app)
    secret = "wrong-password-do-not-log-me"
    response = anonymous.post(
        "/api/auth/login", json={"username": "nobody_at_all", "password": secret}
    )
    assert response.status_code == 401

    page = _events(admin_client, event_type="AUTH_LOGIN_FAILED")
    assert page["returned"] >= 1, "a refused sign-in must outlive the transaction it failed in"

    entry = page["events"][-1]
    assert entry["outcome"] == "REFUSED"
    # The claimed username is recorded as a claim, never as a proven identity.
    assert entry["actor_source"] == "UNAUTHENTICATED"
    assert entry["actor_id"].startswith("unauthenticated:")
    assert secret not in str(entry), "the submitted password must never be recorded"


def test_a_successful_login_is_recorded_as_an_authenticated_act(admin_client):
    page = _events(admin_client, event_type="AUTH_LOGIN_SUCCEEDED")
    assert page["returned"] >= 1
    assert page["events"][-1]["actor_source"] == "AUTHENTICATED_SESSION"
