"""The audit log: what it records, what it refuses, and what it can detect.

These tests are organised around the claims the audit layer makes, because a
claim nobody tests is a claim the system does not actually make.

The tamper tests deliberately reach past the application and modify the SQLite
rows directly. That is the threat the chain exists for: someone who can edit
storage. Going through the application would only prove the application has no
edit method, which is a different property and is tested separately.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from oblivion.core.audit import (
    ActorSource,
    AuditActor,
    AuditAppendError,
    AuditChainStatus,
    AuditError,
    AuditEventType,
    AuditLinkStatus,
    AuditLog,
    AuditOutcome,
    AuditQuery,
    AuditRecord,
    StoredAuditRecord,
    new_audit_id,
    verify_audit_chain,
)
from oblivion.core.evidence.canonicalize import CANONICALIZATION_VERSION
from oblivion.persistence.database import (
    get_engine,
    get_session_factory,
    init_db,
    reset_engine,
)


@pytest.fixture
def audit_session(tmp_path, monkeypatch):
    """A session against a database private to this test.

    The audit log is global and monotonic by design - sequences continue from
    whatever is already stored. Sharing one database across tests would
    therefore make every assertion about sequence numbers, record counts and
    chain status depend on the order the tests happened to run in, and a
    tamper-injection test would poison every test after it. Each test gets its
    own file so the chain under examination is exactly the one it built.
    """
    monkeypatch.setenv("OBLIVION_DATABASE_URL", f"sqlite:///{(tmp_path / 'audit.db').as_posix()}")
    reset_engine()
    init_db()
    factory = get_session_factory()
    try:
        with factory() as session:
            yield session
    finally:
        reset_engine()


def _actor(user: str = "u_alice", role: str = "INVESTIGATOR") -> AuditActor:
    return AuditActor.authenticated(user, role)


def _append_three(session) -> tuple[AuditLog, list[AuditRecord]]:
    log = AuditLog(session)
    records = [
        log.append(
            AuditEventType.AUTH_LOGIN_SUCCEEDED,
            AuditOutcome.SUCCEEDED,
            _actor(),
            summary="signed in",
        ),
        log.append(
            AuditEventType.OPERATION_CREATED,
            AuditOutcome.SUCCEEDED,
            _actor(),
            operation_id="op_chain",
            target_identity=r"C:\scratch\file.txt",
            safe_metadata={"mode": "COMPLETE_ERASURE"},
        ),
        log.append(
            AuditEventType.OPERATION_APPROVED,
            AuditOutcome.SUCCEEDED,
            _actor("u_bob", "ADMIN"),
            operation_id="op_chain",
        ),
    ]
    session.commit()
    return log, records


# ---------------------------------------------------------------------------
# 1. The actor is server-derived and its provenance is recorded
# ---------------------------------------------------------------------------


def test_actor_provenance_is_recorded_distinctly():
    """An authenticated identity and a claimed one must never look alike."""
    authenticated = AuditActor.authenticated("u_alice", "ADMIN")
    system = AuditActor.system("erasure_engine")
    claimed = AuditActor.unauthenticated("alice")

    assert authenticated.source is ActorSource.AUTHENTICATED_SESSION
    assert system.source is ActorSource.SYSTEM
    assert claimed.source is ActorSource.UNAUTHENTICATED

    # The claim is marked in the id itself, so even a reader who ignores
    # actor_source cannot mistake it for a proven principal.
    assert claimed.actor_id.startswith("unauthenticated:")
    assert authenticated.actor_id == "u_alice"


def test_actor_provenance_is_part_of_the_digest():
    """Re-labelling a claimed identity as authenticated must break the digest."""
    base = dict(
        audit_id=new_audit_id(),
        sequence=1,
        event_type=AuditEventType.AUTH_LOGIN_FAILED,
        outcome=AuditOutcome.REFUSED,
        occurred_at=datetime.now(UTC),
    )
    claimed = AuditRecord(actor=AuditActor.unauthenticated("alice"), **base)
    promoted = AuditRecord(actor=AuditActor.authenticated("alice", "ADMIN"), **base)
    assert claimed.digest() != promoted.digest()


def test_an_actor_without_an_id_is_refused():
    with pytest.raises(AuditError, match="actor_id is required"):
        AuditActor(actor_id="", actor_role="ADMIN", source=ActorSource.AUTHENTICATED_SESSION)


# ---------------------------------------------------------------------------
# 2. Append-only: the surface offers no way to change history
# ---------------------------------------------------------------------------


def test_audit_log_exposes_no_mutation_methods():
    """Append-only is a property of the API surface, not a promise."""
    forbidden = {"update", "delete", "edit", "remove", "truncate", "purge", "rewrite"}
    present = {name for name in dir(AuditLog) if not name.startswith("_")}
    assert not (forbidden & present), f"AuditLog exposes mutation methods: {forbidden & present}"


def test_no_audit_route_offers_a_write_verb():
    """The HTTP surface must publish query and verify, and nothing that edits."""
    from oblivion.api.routes.audit import router

    published = {
        (method, route.path)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert ("GET", "/api/audit/events") in published
    assert ("POST", "/api/audit/verify") in published

    for method, path in published:
        assert method not in {"PUT", "PATCH", "DELETE"}, f"{method} {path} can alter history"


# ---------------------------------------------------------------------------
# 3-8. Chain semantics, each state reached deliberately
# ---------------------------------------------------------------------------


def test_valid_genesis_and_valid_predecessors(audit_session):
    _append_three(audit_session)

    # A *fresh* session, so the records are genuinely reloaded from storage
    # rather than verified against the objects that created them.
    with get_session_factory()() as fresh:
        result = AuditLog(fresh).verify()

    assert result.status is AuditChainStatus.INTACT
    assert result.checked == 3
    assert [link.status for link in result.links] == [
        AuditLinkStatus.VALID_GENESIS,
        AuditLinkStatus.VALID_PREDECESSOR,
        AuditLinkStatus.VALID_PREDECESSOR,
    ]


def test_an_empty_log_is_unverifiable_not_intact(audit_session):
    result = AuditLog(audit_session).verify()
    assert result.status is AuditChainStatus.UNVERIFIABLE
    assert result.proves == ()


def test_a_mutated_event_is_detected_and_named(audit_session):
    _append_three(audit_session)

    # Tamper below the application, as someone with database access would.
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE audit_events SET actor_id='u_mallory' WHERE sequence=2"))

    with get_session_factory()() as fresh:
        result = AuditLog(fresh).verify()

    assert result.status is AuditChainStatus.BROKEN
    statuses = [link.status for link in result.links]
    # The edited record is named as edited; its successor separately reports a
    # predecessor that no longer matches.
    assert statuses[1] is AuditLinkStatus.MUTATED_EVENT
    assert statuses[2] is AuditLinkStatus.BROKEN_PREDECESSOR
    assert result.proves == ()


def test_a_deleted_middle_record_is_detected(audit_session):
    _append_three(audit_session)

    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM audit_events WHERE sequence=2"))

    with get_session_factory()() as fresh:
        result = AuditLog(fresh).verify()

    assert result.status is AuditChainStatus.BROKEN
    assert AuditLinkStatus.MISSING_PREDECESSOR in {link.status for link in result.links}


def test_a_broken_predecessor_digest_is_distinguished_from_a_mutation():
    """A record whose recorded predecessor digest is wrong, but which is itself intact."""
    first = AuditRecord(
        audit_id="aud_first",
        sequence=1,
        event_type=AuditEventType.AUTH_LOGIN_SUCCEEDED,
        outcome=AuditOutcome.SUCCEEDED,
        actor=_actor(),
        occurred_at=datetime.now(UTC),
    )
    second = AuditRecord(
        audit_id="aud_second",
        sequence=2,
        event_type=AuditEventType.OPERATION_CREATED,
        outcome=AuditOutcome.SUCCEEDED,
        actor=_actor(),
        occurred_at=datetime.now(UTC),
        previous_audit_id="aud_first",
        previous_audit_digest="f" * 64,  # not the real digest of `first`
    )
    result = verify_audit_chain(
        [
            StoredAuditRecord(first, first.digest()),
            StoredAuditRecord(second, second.digest()),
        ]
    )
    assert result.status is AuditChainStatus.BROKEN
    assert result.links[1].status is AuditLinkStatus.BROKEN_PREDECESSOR


def test_a_window_that_does_not_start_at_genesis_is_unverifiable():
    """Internally consistent, but silent about the history before it."""
    second = AuditRecord(
        audit_id="aud_second",
        sequence=2,
        event_type=AuditEventType.OPERATION_CREATED,
        outcome=AuditOutcome.SUCCEEDED,
        actor=_actor(),
        occurred_at=datetime.now(UTC),
        previous_audit_id="aud_first",
        previous_audit_digest="a" * 64,
    )
    result = verify_audit_chain([StoredAuditRecord(second, second.digest())])
    assert result.status is AuditChainStatus.UNVERIFIABLE
    assert result.links[0].status is AuditLinkStatus.MISSING_PREDECESSOR


def test_a_record_after_genesis_must_reference_a_predecessor():
    with pytest.raises(AuditError, match="must reference its predecessor"):
        AuditRecord(
            audit_id="aud_x",
            sequence=2,
            event_type=AuditEventType.AUTH_LOGOUT,
            outcome=AuditOutcome.SUCCEEDED,
            actor=_actor(),
            occurred_at=datetime.now(UTC),
        )


def test_the_genesis_record_cannot_reference_a_predecessor():
    with pytest.raises(AuditError, match="first record cannot reference"):
        AuditRecord(
            audit_id="aud_x",
            sequence=1,
            event_type=AuditEventType.AUTH_LOGOUT,
            outcome=AuditOutcome.SUCCEEDED,
            actor=_actor(),
            occurred_at=datetime.now(UTC),
            previous_audit_id="aud_w",
            previous_audit_digest="b" * 64,
        )


# ---------------------------------------------------------------------------
# 9. Verification reads persisted records, and round-trips exactly
# ---------------------------------------------------------------------------


def test_persisted_record_rehashes_to_its_stored_digest(audit_session):
    """The round-trip hazard: what was hashed must be what comes back."""
    _append_three(audit_session)

    with get_session_factory()() as fresh:
        stored = AuditLog(fresh).query_stored(AuditQuery(limit=10))

    assert len(stored) == 3
    for entry in stored:
        assert entry.record.digest() == entry.stored_digest
    # And specifically the timezone-aware instant survived storage.
    assert stored[0].record.occurred_at.tzinfo is not None
    assert stored[0].record.canonicalization_version == CANONICALIZATION_VERSION


def test_metadata_round_trips_as_structured_data(audit_session):
    log = AuditLog(audit_session)
    log.append(
        AuditEventType.OPERATION_CREATED,
        AuditOutcome.SUCCEEDED,
        _actor(),
        operation_id="op_meta",
        safe_metadata={"mode": "SELECTIVE_PERMANENT", "count": 3, "dry_run": False},
    )
    audit_session.commit()

    with get_session_factory()() as fresh:
        entries = AuditLog(fresh).query_stored(AuditQuery(operation_id="op_meta"))

    meta = entries[0].record.safe_metadata
    assert meta == {"mode": "SELECTIVE_PERMANENT", "count": 3, "dry_run": False}
    assert isinstance(meta["count"], int)
    assert meta["dry_run"] is False


# ---------------------------------------------------------------------------
# 10. Non-self-authenticating: the caller cannot supply the verdict
# ---------------------------------------------------------------------------


def test_verify_request_has_no_field_for_a_verdict():
    from oblivion.api.schemas.audit import AuditVerifyRequest

    fields = set(AuditVerifyRequest.model_fields)
    assert fields == {"operation_id"}, (
        "The verify request must carry no digest, record or expected status: "
        "anything else would let the caller contribute to the answer."
    )


def test_a_record_cannot_vouch_for_itself(audit_session):
    """Rewriting a row's own digest to match its edited content is still detected.

    The successor's recorded predecessor digest is the second, independent
    binding, and a tamperer who edits one record cannot satisfy it without also
    rewriting every record that follows.
    """
    _append_three(audit_session)

    with get_session_factory()() as fresh:
        entries = AuditLog(fresh).query_stored(AuditQuery(limit=10))
    victim = entries[1].record

    # Edit the content *and* recompute a matching digest, as a careful attacker
    # would.
    edited = AuditRecord(
        audit_id=victim.audit_id,
        sequence=victim.sequence,
        event_type=victim.event_type,
        outcome=victim.outcome,
        actor=AuditActor.authenticated("u_mallory", "ADMIN"),
        occurred_at=victim.occurred_at,
        operation_id=victim.operation_id,
        target_identity=victim.target_identity,
        summary=victim.summary,
        safe_metadata=victim.safe_metadata,
        previous_audit_id=victim.previous_audit_id,
        previous_audit_digest=victim.previous_audit_digest,
    )
    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE audit_events SET actor_id=:a, digest=:d WHERE id=:i"),
            {"a": "u_mallory", "d": edited.digest(), "i": victim.audit_id},
        )

    with get_session_factory()() as fresh:
        result = AuditLog(fresh).verify()

    # Its own digest now agrees, so it is not reported as MUTATED - but the
    # record after it still names the old digest, and that is what fails.
    assert result.status is AuditChainStatus.BROKEN
    assert result.links[2].status is AuditLinkStatus.BROKEN_PREDECESSOR


# ---------------------------------------------------------------------------
# 11. Secrets can never enter the log
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "password",
        "vault_key",
        "private_key",
        "session_token",
        "api_key",
        "recovery_key",
        "bearer_credential",
    ],
)
def test_metadata_field_names_suggesting_secrets_are_refused(field):
    with pytest.raises(AuditError, match="forbidden pattern"):
        AuditRecord(
            audit_id=new_audit_id(),
            sequence=1,
            event_type=AuditEventType.AUTH_LOGIN_SUCCEEDED,
            outcome=AuditOutcome.SUCCEEDED,
            actor=_actor(),
            occurred_at=datetime.now(UTC),
            safe_metadata={field: "value"},
        )


def test_the_append_path_also_refuses_secret_field_names(audit_session):
    with pytest.raises(AuditError, match="forbidden pattern"):
        AuditLog(audit_session).append(
            AuditEventType.AUTH_LOGIN_SUCCEEDED,
            AuditOutcome.SUCCEEDED,
            _actor(),
            safe_metadata={"password": "hunter2"},
        )


# ---------------------------------------------------------------------------
# 12. A reader can reconstruct what happened
# ---------------------------------------------------------------------------


def test_a_record_answers_what_who_when_and_which(audit_session):
    log = AuditLog(audit_session)
    record = log.append(
        AuditEventType.OPERATION_EXECUTED,
        AuditOutcome.SUCCEEDED,
        _actor("u_operator", "OPERATOR"),
        operation_id="op_reconstruct",
        target_identity=r"C:\scratch\evidence.bin",
        evidence_id="ev_123",
        certificate_id="cert_456",
        summary="Executed the approved erasure.",
        safe_metadata={"policy_id": "ERASURE.STANDARD.V1"},
    )
    audit_session.commit()

    assert record.event_type is AuditEventType.OPERATION_EXECUTED  # WHAT
    assert record.actor.actor_id == "u_operator"  # WHO
    assert record.actor.actor_role == "OPERATOR"  # on what authority
    assert record.occurred_at.tzinfo is not None  # WHEN
    assert record.operation_id == "op_reconstruct"  # WHICH operation
    assert record.target_identity.endswith("evidence.bin")  # WHICH target
    assert record.evidence_id == "ev_123"  # what was observed
    assert record.certificate_id == "cert_456"  # what was decided
    assert record.outcome is AuditOutcome.SUCCEEDED


def test_refused_and_failed_remain_distinct(audit_session):
    log = AuditLog(audit_session)
    refused = log.append(
        AuditEventType.OPERATION_APPROVAL_REFUSED,
        AuditOutcome.REFUSED,
        _actor(),
        operation_id="op_sod",
        summary="Self-approval refused.",
    )
    failed = log.append(
        AuditEventType.OPERATION_EXECUTED,
        AuditOutcome.FAILED,
        _actor(),
        operation_id="op_sod",
    )
    audit_session.commit()
    assert refused.outcome is not failed.outcome
    assert refused.digest() != failed.digest()


# ---------------------------------------------------------------------------
# 13. Audit-chain integrity is not evidence integrity
# ---------------------------------------------------------------------------


def test_an_intact_chain_makes_no_claim_about_evidence_or_erasure(audit_session):
    _append_three(audit_session)
    with get_session_factory()() as fresh:
        result = AuditLog(fresh).verify()

    assert result.status is AuditChainStatus.INTACT
    joined = " ".join(result.does_not_prove).lower()
    assert "erasure" in joined
    assert "evidence integrity" in joined
    assert "certificate" in joined
    # And nothing in `proves` strays beyond the log itself.
    for claim in result.proves:
        assert "record" in claim.lower()


def test_the_audit_chain_does_not_reimplement_the_evidence_chain():
    """One canonicalizer, one digest definition - reused, not duplicated."""
    import oblivion.core.audit.records as audit_records

    with open(audit_records.__file__, encoding="utf-8") as handle:
        source = handle.read()

    # The audit record imports the evidence canonicalizer and the evidence
    # secret-pattern list rather than defining its own.
    assert "from oblivion.core.evidence.canonicalize import" in source
    assert "FORBIDDEN_FIELD_PATTERNS" in source
    assert "def canonicalize(" not in source, "a second canonicalizer is a competing model"


# ---------------------------------------------------------------------------
# 14. Sequence assignment and durability
# ---------------------------------------------------------------------------


def test_sequence_is_read_from_storage_not_from_memory(audit_session):
    """A new log object must continue the numbering, not restart it."""
    _append_three(audit_session)

    with get_session_factory()() as fresh:
        record = AuditLog(fresh).append(
            AuditEventType.AUTH_LOGOUT, AuditOutcome.SUCCEEDED, _actor()
        )
        fresh.commit()

    assert record.sequence == 4
    assert record.previous_audit_id is not None


def test_appending_onto_a_digestless_tail_is_refused(audit_session):
    """A legacy row cannot be linked to honestly, so it is not linked to at all."""
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_events (id, sequence, event_type, outcome, actor_id,"
                " created_at) VALUES ('aud_legacy', 9999, 'OPERATION_CREATED', 'OK',"
                " 'system', CURRENT_TIMESTAMP)"
            )
        )

    with get_session_factory()() as fresh, pytest.raises(AuditAppendError, match="no digest"):
        AuditLog(fresh).append(AuditEventType.AUTH_LOGOUT, AuditOutcome.SUCCEEDED, _actor())


def test_records_predating_the_chain_are_counted_not_hidden(audit_session):
    _append_three(audit_session)
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_events (id, sequence, event_type, outcome, actor_id,"
                " safe_metadata, created_at) VALUES ('aud_legacy2', 0,"
                " 'OPERATION_CREATED', 'OK', 'system', :meta, CURRENT_TIMESTAMP)"
            ),
            {"meta": "{'state': 'X'}"},
        )

    with get_session_factory()() as fresh:
        result = AuditLog(fresh).verify()

    assert result.records_predating_chain == 1
    # Their existence is disclosed in the limits, never folded into the verdict.
    assert any("before" in claim for claim in result.does_not_prove)


# ---------------------------------------------------------------------------
# 15. Filters
# ---------------------------------------------------------------------------


def test_queries_filter_without_inventing_records(audit_session):
    _append_three(audit_session)
    with get_session_factory()() as fresh:
        log = AuditLog(fresh)
        by_operation = log.query(AuditQuery(operation_id="op_chain"))
        by_type = log.query(AuditQuery(event_type=AuditEventType.OPERATION_APPROVED))
        by_missing = log.query(AuditQuery(operation_id="op_does_not_exist"))

    assert {r.event_type for r in by_operation} == {
        AuditEventType.OPERATION_CREATED,
        AuditEventType.OPERATION_APPROVED,
    }
    assert len(by_type) == 1
    assert by_missing == []


def test_time_filters_use_the_canonical_instant(audit_session):
    log = AuditLog(audit_session)
    old = datetime.now(UTC) - timedelta(days=2)
    log.append(
        AuditEventType.AUTH_LOGIN_SUCCEEDED,
        AuditOutcome.SUCCEEDED,
        _actor(),
        occurred_at=old,
    )
    log.append(AuditEventType.AUTH_LOGOUT, AuditOutcome.SUCCEEDED, _actor())
    audit_session.commit()

    cutoff = datetime.now(UTC) - timedelta(days=1)
    with get_session_factory()() as fresh:
        recent = AuditLog(fresh).query(AuditQuery(since=cutoff))
        earlier = AuditLog(fresh).query(AuditQuery(until=cutoff))

    assert [r.event_type for r in recent] == [AuditEventType.AUTH_LOGOUT]
    assert [r.event_type for r in earlier] == [AuditEventType.AUTH_LOGIN_SUCCEEDED]


def test_a_naive_timestamp_is_refused(audit_session):
    with pytest.raises(AuditError, match="timezone-aware"):
        AuditRecord(
            audit_id=new_audit_id(),
            sequence=1,
            event_type=AuditEventType.AUTH_LOGOUT,
            outcome=AuditOutcome.SUCCEEDED,
            actor=_actor(),
            occurred_at=datetime.now(),  # noqa: DTZ005 - the point of the test
        )


# ---------------------------------------------------------------------------
# 16. The stored form is canonical JSON, never a Python repr
# ---------------------------------------------------------------------------


def test_stored_metadata_is_canonical_json(audit_session):
    log = AuditLog(audit_session)
    log.append(
        AuditEventType.OPERATION_CREATED,
        AuditOutcome.SUCCEEDED,
        _actor(),
        operation_id="op_json",
        safe_metadata={"b": 2, "a": 1},
    )
    audit_session.commit()

    with get_engine().begin() as conn:
        raw = conn.execute(
            text("SELECT safe_metadata FROM audit_events WHERE operation_id='op_json'")
        ).scalar_one()

    # Parseable, and in canonical key order.
    assert json.loads(raw) == {"a": 1, "b": 2}
    assert raw == '{"a":1,"b":2}'
