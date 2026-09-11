"""F-D: the operations listing endpoint.

The console had an operations ledger and the contract published no way to fill
it, so an operator had to paste an operation ID into the address bar to reach
anything. This endpoint closes that gap.

What these tests hold it to: it is authenticated, it is permission-gated, it
filters in the database, it pages, and every value it returns comes from a
persisted row. Nothing about an operation is synthesised - not the identifier,
not the state, not the progress.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from oblivion.api import app
from oblivion.core.state.machine import State
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.operation_repo import OperationRepository

SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"


@pytest.fixture(autouse=True)
def database():
    init_db()


def make_operation(temp_dir, *, state=State.PENDING_APPROVAL.name, requested_by="u_req"):
    """Persist one target and one operation. Returns (operation_id, target_id)."""
    suffix = uuid.uuid4().hex[:8]
    target_path = temp_dir / f"listed_{suffix}.txt"
    target_path.write_text("payload", encoding="utf-8")

    session_factory = get_session_factory()
    with session_factory() as session:
        repo = OperationRepository(session)
        repo.create_target(
            target_id=f"tgt_{suffix}",
            path=str(target_path),
            canonical_path=str(target_path),
            target_type="file",
        )
        repo.create_operation(
            operation_id=f"op_{suffix}",
            target_id=f"tgt_{suffix}",
            mode="SELECTIVE_PERMANENT",
            policy_id=SELECTIVE_POLICY,
            state=state,
            requested_by=requested_by,
        )
        session.commit()
    return f"op_{suffix}", f"tgt_{suffix}"


def listing(client, **params):
    response = client.get("/api/operations", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Authentication and authorization
# ---------------------------------------------------------------------------


def test_listing_requires_authentication():
    """401, and distinguishably so - not 403 and not an empty page."""
    anonymous = TestClient(app)
    response = anonymous.get("/api/operations")
    assert response.status_code == 401
    assert response.json()["error_code"] in {"UNAUTHENTICATED", "SESSION_INVALID"}


@pytest.mark.parametrize(
    "fixture_name",
    ["admin_client", "operator_client", "auditor_client", "viewer_client"],
)
def test_every_role_holding_operation_view_may_list(fixture_name, request, temp_dir):
    """The existing authorization model, unchanged: `operation.view` governs this."""
    make_operation(temp_dir)
    client = request.getfixturevalue(fixture_name)
    assert client.get("/api/operations").status_code == 200


def test_the_listing_exposes_no_audit_or_evidence_material(admin_client, temp_dir):
    """This is an operations route, not a general database listing."""
    make_operation(temp_dir)
    body = listing(admin_client)

    assert body["operations"], "expected at least the operation just created"
    for operation in body["operations"]:
        for forbidden in (
            "digest",
            "signature",
            "public_key",
            "safe_metadata",
            "actor_source",
        ):
            assert forbidden not in operation, (
                f"{forbidden} belongs to the audit or certificate surface and must "
                "not leak through the operations listing"
            )


# ---------------------------------------------------------------------------
# The rows come from storage
# ---------------------------------------------------------------------------


def test_a_created_operation_appears_with_its_persisted_state(admin_client, temp_dir):
    operation_id, target_id = make_operation(temp_dir)
    body = listing(admin_client)

    match = next((o for o in body["operations"] if o["id"] == operation_id), None)
    assert match is not None, "a persisted operation must be listed"
    assert match["state"] == State.PENDING_APPROVAL.name
    assert match["target_id"] == target_id
    assert match["mode"] == "SELECTIVE_PERMANENT"


def test_nothing_is_returned_for_an_empty_result(admin_client):
    """An operation that does not exist simply does not appear."""
    body = listing(admin_client, operation_id="op_does_not_exist")
    assert body["operations"] == []
    assert body["returned"] == 0


# ---------------------------------------------------------------------------
# Filtering happens server-side
# ---------------------------------------------------------------------------


def test_filtering_by_state(admin_client, temp_dir):
    pending_id, _ = make_operation(temp_dir, state=State.PENDING_APPROVAL.name)
    ready_id, _ = make_operation(temp_dir, state=State.READY.name)

    ready = listing(admin_client, state=State.READY.name)
    ids = {o["id"] for o in ready["operations"]}

    assert ready_id in ids
    assert pending_id not in ids
    assert all(o["state"] == State.READY.name for o in ready["operations"])


def test_filtering_by_operation_id(admin_client, temp_dir):
    wanted, _ = make_operation(temp_dir)
    make_operation(temp_dir)

    body = listing(admin_client, operation_id=wanted)
    assert [o["id"] for o in body["operations"]] == [wanted]


def test_filtering_by_requester(admin_client, temp_dir):
    mine, _ = make_operation(temp_dir, requested_by="u_alice")
    theirs, _ = make_operation(temp_dir, requested_by="u_bob")

    body = listing(admin_client, requested_by="u_alice")
    ids = {o["id"] for o in body["operations"]}
    assert mine in ids
    assert theirs not in ids


def test_filtering_by_target(admin_client, temp_dir):
    wanted, target_id = make_operation(temp_dir)
    other, _ = make_operation(temp_dir)

    body = listing(admin_client, target_id=target_id)
    ids = {o["id"] for o in body["operations"]}
    assert wanted in ids
    assert other not in ids


def test_an_unknown_state_filter_is_refused_not_ignored(admin_client):
    """A dropped filter returns more than was asked for while looking correct."""
    response = admin_client.get("/api/operations", params={"state": "NOT_A_STATE"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "UNKNOWN_OPERATION_STATE"


# ---------------------------------------------------------------------------
# Paging
# ---------------------------------------------------------------------------


def test_the_total_is_the_whole_result_not_the_page(admin_client, temp_dir):
    # A requester unique to this run. The suite shares one SQLite file and rows
    # accumulate across invocations, so a fixed name would count operations left
    # behind by earlier runs and the assertion would drift with history rather
    # than measure this test.
    requester = f"u_pager_{uuid.uuid4().hex[:8]}"
    for _ in range(3):
        make_operation(temp_dir, requested_by=requester)

    page = listing(admin_client, requested_by=requester, limit=2)

    assert page["returned"] == 2
    assert page["limit"] == 2
    # The point of carrying `total`: a reader can tell a window from everything
    # without inferring it from the page happening to be full.
    assert page["total"] == 3


def test_offset_moves_through_the_result(admin_client, temp_dir):
    requester = f"u_offset_{uuid.uuid4().hex[:8]}"
    for _ in range(3):
        make_operation(temp_dir, requested_by=requester)

    first = listing(admin_client, requested_by=requester, limit=2, offset=0)
    second = listing(admin_client, requested_by=requester, limit=2, offset=2)

    first_ids = {o["id"] for o in first["operations"]}
    second_ids = {o["id"] for o in second["operations"]}

    assert len(first_ids) == 2
    assert len(second_ids) == 1
    assert first_ids.isdisjoint(second_ids), "pages must not repeat rows"


def test_the_page_size_is_bounded(admin_client):
    """A read must not be turnable into a denial of service."""
    assert admin_client.get("/api/operations", params={"limit": 100000}).status_code == 422
