"""Tests for Phase 17 persistent database layer."""
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import inspect

from oblivion.persistence import database
from oblivion.persistence.database import get_engine, init_db, reset_engine
from oblivion.persistence.models import (
    OperationModel,
    UserModel,
)
from oblivion.persistence.repositories import (
    AuditRepository,
    CertificateRepository,
    EvidenceRepository,
    OperationRepository,
)


@pytest.fixture
def temp_db(monkeypatch):
    """Creates a temporary SQLite database for the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        monkeypatch.setenv("OBLIVION_DATABASE_URL", f"sqlite:///{db_path}")
        reset_engine()
        init_db()
        yield f"sqlite:///{db_path}"
        reset_engine()


def test_database_initialization(temp_db):
    """Verify that init_db creates all expected tables."""
    engine = get_engine()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected = {
        "users", "roles", "permissions", "role_permissions", "sessions",
        "targets", "operations", "operation_events",
        "baselines", "recovery_tests", "residual_findings", "assurance_results",
        "evidence_records", "certificates", "audit_events",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_empty_database_startup(temp_db):
    """Verify the application can start with an empty database."""
    SessionLocal = database.get_session_factory()
    session = SessionLocal()
    try:
        assert session.query(UserModel).count() == 0
        assert session.query(OperationModel).count() == 0
    finally:
        session.close()


def test_operation_crud(temp_db):
    """Test basic CRUD on operations and events."""
    SessionLocal = database.get_session_factory()
    session = SessionLocal()
    try:
        repo = OperationRepository(session)
        target = repo.create_target(
            target_id="t1", path="/tmp/a", canonical_path="/tmp/a", target_type="file", sha256="abc"
        )
        op = repo.create_operation(operation_id="op1", target_id=target.id, mode="SELECTIVE_PERMANENT")
        ev = repo.append_event(event_id="e1", operation_id="op1", sequence=1, event_type="STATE_CHANGE", to_state="ANALYZING")
        session.commit()

        op_loaded = repo.get_operation("op1")
        assert op_loaded is not None
        assert op_loaded.state == "CREATED"
        assert op_loaded.target.path == "/tmp/a"

        repo.update_operation_state("op1", "ANALYZING")
        session.commit()
        assert repo.get_operation("op1").state == "ANALYZING"
    finally:
        session.close()


def test_evidence_crud(temp_db):
    """Test evidence persistence."""
    SessionLocal = database.get_session_factory()
    session = SessionLocal()
    try:
        op_repo = OperationRepository(session)
        ev_repo = EvidenceRepository(session)

        target = op_repo.create_target(target_id="t1", path="/tmp/b", canonical_path="/tmp/b", target_type="file")
        op_repo.create_operation("op1", target.id, "COMPLETE_ERASURE")

        baseline = ev_repo.create_baseline("b1", "op1", target.id, hashes='{"sha256":"abc"}')
        recovery = ev_repo.create_recovery_test("rt1", "op1", "NOT_DETECTED")
        finding = ev_repo.create_residual_finding("f1", "op1", "LOW", "no residual")
        assurance = ev_repo.create_assurance_result("a1", "op1", "PASSED", "HIGH")
        session.commit()

        assert ev_repo.get_assurance_result("op1") is not None
        assert ev_repo.get_assurance_result("op1").status == "PASSED"
    finally:
        session.close()


def test_certificate_persistence(temp_db):
    """Test certificate and evidence record persistence."""
    SessionLocal = database.get_session_factory()
    session = SessionLocal()
    try:
        op_repo = OperationRepository(session)
        cert_repo = CertificateRepository(session)

        target = op_repo.create_target(target_id="t1", path="/tmp/c", canonical_path="/tmp/c", target_type="file")
        op_repo.create_operation("op1", target.id, "SELECTIVE_PERMANENT")

        er = cert_repo.create_evidence_record(
            "er1", "op1", "a" * 64, payload='{"operation_id": "op1"}'
        )
        cert = cert_repo.create_certificate(
            cert_id="c1", operation_id="op1", evidence_digest="a" * 64,
            public_key="pk", signature="sig", claim="test claim"
        )
        session.commit()

        loaded = cert_repo.get_certificate("c1")
        assert loaded is not None
        assert loaded.signing_algorithm == "Ed25519"
        assert loaded.claim == "test claim"
    finally:
        session.close()


def test_audit_event_persistence(temp_db):
    SessionLocal = database.get_session_factory()
    session = SessionLocal()
    try:
        repo = AuditRepository(session)
        ev = repo.append("a1", "TEST_EVENT", "SUCCESS", actor_id="u1", operation_id="op1")
        session.commit()
        assert ev.id == "a1"
    finally:
        session.close()


def test_rollback_on_error(temp_db):
    """Verify that errors cause a rollback and no partial state remains."""
    SessionLocal = database.get_session_factory()
    session = SessionLocal()
    try:
        op_repo = OperationRepository(session)
        target = op_repo.create_target(target_id="t1", path="/tmp/d", canonical_path="/tmp/d", target_type="file")
        op_repo.create_operation("op1", target.id, "SELECTIVE_PERMANENT")
        session.commit()

        # Try to create a duplicate user (primary key conflict) to force a real error
        user1 = UserModel(id="u1", username="duplicate")
        session.add(user1)
        session.commit()

        user2 = UserModel(id="u2", username="duplicate")  # same username -> IntegrityError
        session.add(user2)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()

        # State machine integrity: op1 and u1 should still be there
        assert op_repo.get_operation("op1") is not None
        assert session.get(UserModel, "u1") is not None
    finally:
        session.close()


def test_crash_recovery_does_not_erase_history(temp_db):
    """Verify that a new session after commit can still see the history."""
    SessionLocal = database.get_session_factory()
    session = SessionLocal()
    try:
        op_repo = OperationRepository(session)
        target = op_repo.create_target(target_id="t1", path="/tmp/e", canonical_path="/tmp/e", target_type="file")
        op_repo.create_operation("op1", target.id, "SELECTIVE_PERMANENT")
        op_repo.append_event("e1", "op1", 1, "STATE_CHANGE", from_state="CREATED", to_state="ANALYZING")
        op_repo.append_event("e2", "op1", 2, "STATE_CHANGE", from_state="ANALYZING", to_state="READY")
        op_repo.append_event("e3", "op1", 3, "STATE_CHANGE", from_state="READY", to_state="ERASING")
        session.commit()
    finally:
        session.close()

    SessionLocal2 = database.get_session_factory()
    session2 = SessionLocal2()
    try:
        op_repo2 = OperationRepository(session2)
        op = op_repo2.get_operation("op1")
        assert op is not None
        events = list(op.events)
        assert len(events) == 3
        assert events[0].from_state == "CREATED"
        assert events[2].to_state == "ERASING"
    finally:
        session2.close()
