"""Phase 25: the closed loop, driven end to end through real code.

Nothing here is simulated. A real file is created, a real approval is persisted,
the privileged service really deletes it, real recovery methods are attempted,
real residual scanners run, and the resulting certificate is verified the way an
independent party would verify it.

The tests are grouped by the claims the pipeline makes, because a pipeline that
produced a certificate without having established the things the certificate
implies would be worse than no pipeline at all.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid

import pytest

from oblivion.certificate.keys import SigningKeyManager, generate_private_key_hex
from oblivion.certificate.trust_model import StaticTrustStore, TrustedKey
from oblivion.core.assurance.models import AnalysisState, AssuranceStatus
from oblivion.core.pipeline import (
    ClosedLoopPipeline,
    PipelineRequest,
    Stage,
    StageStatus,
)
from oblivion.core.recovery.testing import MethodOutcome, RecoveryMethod, RecoveryTester
from oblivion.core.residual.scanners import ResidualScanSuite
from oblivion.core.state.machine import State
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.certificate_repo import CertificateRepository
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.privileged import (
    InProcessTransport,
    PrivilegedClient,
    PrivilegedService,
    RequestAuthenticator,
    ServiceConfig,
)

SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"
SIGNER_ID = "oblivion-issuer"
REQUESTER = "user_investigator_1"
APPROVER = "user_admin_1"


@pytest.fixture(autouse=True)
def database():
    init_db()


@pytest.fixture
def privileged_client(safe_validator):
    """A real privileged service, reached through the real client."""
    authenticator = RequestAuthenticator(bytes.fromhex(secrets.token_hex(32)))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    return PrivilegedClient(InProcessTransport(service), authenticator)


@pytest.fixture
def key_manager():
    return SigningKeyManager.from_material(generate_private_key_hex())


@pytest.fixture
def trust_store(key_manager):
    """A trust store that trusts this signer because it was configured to."""
    return StaticTrustStore.from_keys(
        [
            TrustedKey(
                signer_id=SIGNER_ID,
                public_key_bytes=key_manager.public_key_bytes(),
            )
        ]
    )


def approve_operation(session, target_path, *, approved=True, self_approved=False):
    """Persist a target and an operation, optionally with a durable approval."""
    suffix = uuid.uuid4().hex[:8]
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
        state=State.READY.name if approved else State.PENDING_APPROVAL.name,
        requested_by=REQUESTER,
        approved_by=(REQUESTER if self_approved else APPROVER) if approved else None,
    )
    session.commit()
    return f"op_{suffix}"


def make_request(operation_id, target_path):
    return PipelineRequest(
        operation_id=operation_id,
        target_path=str(target_path),
        target_type="file",
        mode="SELECTIVE_PERMANENT",
        policy_id=SELECTIVE_POLICY,
        actor_id=APPROVER,
    )


def run_pipeline(safe_validator, privileged_client, target_path, **kwargs):
    """Run the whole loop against a persisted, approved operation."""
    session_factory = get_session_factory()
    with session_factory() as session:
        operation_id = approve_operation(
            session,
            target_path,
            approved=kwargs.pop("approved", True),
            self_approved=kwargs.pop("self_approved", False),
        )
        pipeline = ClosedLoopPipeline(
            session=session,
            validator=safe_validator,
            privileged=privileged_client,
            **kwargs,
        )
        result = pipeline.run(make_request(operation_id, target_path))
        session.commit()
    return result


# ---------------------------------------------------------------------------
# The complete loop
# ---------------------------------------------------------------------------


def test_a_full_operation_runs_every_stage(
    safe_validator, privileged_client, key_manager, trust_store, temp_dir
):
    """The demonstration: file exists, is erased, and the claim is verifiable.

    This is the trace the whole system exists to produce - and every step of it
    is performed by production code, not by the test.
    """
    target = temp_dir / "confidential.txt"
    target.write_text("sensitive payload")
    assert target.exists()

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        trust_store=trust_store,
    )

    # 1. the file is gone
    assert not target.exists()

    # 2. every stage ran
    assert set(result.completed_stages) >= {
        Stage.DISCOVER,
        Stage.BASELINE,
        Stage.RECOMMEND,
        Stage.AUTHORIZE,
        Stage.ERASE,
        Stage.VALIDATE,
        Stage.TEST_RECOVERY,
        Stage.ANALYZE_RESIDUALS,
        Stage.ASSESS_ASSURANCE,
        Stage.GENERATE_EVIDENCE,
        Stage.ISSUE_CERTIFICATE,
        Stage.VERIFY_CERTIFICATE,
    }

    # 3. evidence and a certificate exist, and the certificate verifies
    assert result.evidence_id
    assert result.evidence_digest
    assert result.certificate_id
    assert result.verification_status == "VALID"
    assert result.final_state == State.COMPLETED.name


def test_the_persisted_certificate_belongs_to_this_operation(
    safe_validator, privileged_client, key_manager, trust_store, temp_dir
):
    """The stored artifacts are the ones the run produced, not placeholders."""
    target = temp_dir / "stored.txt"
    target.write_text("payload")

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        trust_store=trust_store,
    )

    session_factory = get_session_factory()
    with session_factory() as session:
        repo = CertificateRepository(session)
        certificate = repo.load_certificate(result.certificate_id)
        evidence = repo.load_evidence(result.evidence_id)

    assert certificate is not None
    assert evidence is not None
    assert certificate.operation_id == result.operation_id
    assert certificate.target_identity == str(target)
    assert evidence.digest() == certificate.evidence_digest


def test_the_operation_record_ends_in_a_terminal_state(
    safe_validator, privileged_client, key_manager, trust_store, temp_dir
):
    """The persisted state reflects what happened, so nothing is left in flight."""
    target = temp_dir / "stateful.txt"
    target.write_text("payload")

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        trust_store=trust_store,
    )

    session_factory = get_session_factory()
    with session_factory() as session:
        operation = OperationRepository(session).get_operation(result.operation_id)

    assert operation.state == State.COMPLETED.name


# ---------------------------------------------------------------------------
# Authorization is durable, and gates everything destructive
# ---------------------------------------------------------------------------


def test_an_unapproved_operation_never_reaches_the_filesystem(
    safe_validator, privileged_client, key_manager, temp_dir
):
    """No approval means no deletion. The file must survive untouched."""
    target = temp_dir / "unapproved.txt"
    target.write_text("must survive")

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        approved=False,
    )

    assert target.exists()
    assert target.read_text() == "must survive"

    authorize = result.outcome(Stage.AUTHORIZE)
    assert authorize.status is StageStatus.REFUSED
    assert result.certificate_id is None
    assert result.final_state == State.FAILED.name


def test_a_self_approved_operation_is_refused(
    safe_validator, privileged_client, key_manager, temp_dir
):
    """Separation of duties, enforced from the persisted record."""
    target = temp_dir / "self-approved.txt"
    target.write_text("must survive")

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        self_approved=True,
    )

    assert target.exists()
    assert result.outcome(Stage.AUTHORIZE).status is StageStatus.REFUSED
    assert "Separation of duties" in result.outcome(Stage.AUTHORIZE).detail
    assert result.certificate_id is None


def test_a_refused_operation_still_produces_evidence(
    safe_validator, privileged_client, key_manager, temp_dir
):
    """Declining is a fact worth recording.

    The evidence names the stages that did not run, so the record shows a
    refusal rather than an operation that simply has no trace.
    """
    target = temp_dir / "refused.txt"
    target.write_text("must survive")

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        approved=False,
    )

    assert result.evidence_id
    assert result.outcome(Stage.ERASE).status is StageStatus.SKIPPED
    assert result.outcome(Stage.ISSUE_CERTIFICATE).status is StageStatus.REFUSED


# ---------------------------------------------------------------------------
# A certificate requires more than a successful delete
# ---------------------------------------------------------------------------


def test_no_signing_identity_means_no_certificate_and_no_crash(
    safe_validator, privileged_client, temp_dir
):
    """An unsigned certificate would be worthless, so none is issued."""
    target = temp_dir / "unsigned.txt"
    target.write_text("payload")

    result = run_pipeline(safe_validator, privileged_client, target)

    assert not target.exists()  # the erasure still happened and is recorded
    assert result.evidence_id
    assert result.certificate_id is None
    assert result.outcome(Stage.ISSUE_CERTIFICATE).status is StageStatus.UNAVAILABLE
    assert result.final_state == State.PARTIAL.name


def test_a_certificate_is_never_issued_without_an_execution(
    safe_validator, privileged_client, key_manager, temp_dir
):
    """The gate the brief calls out by name.

    A deletion that never happened cannot be certified, whatever else succeeded.
    """
    target = temp_dir / "never-executed.txt"
    target.write_text("payload")

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        approved=False,
    )

    assert result.outcome(Stage.ISSUE_CERTIFICATE).status is StageStatus.REFUSED
    assert result.certificate_id is None


def test_an_unknown_signer_cannot_yield_a_valid_verification(
    safe_validator, privileged_client, key_manager, temp_dir
):
    """A signature verifies; trust is a separate question with a separate answer."""
    target = temp_dir / "untrusted.txt"
    target.write_text("payload")

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        trust_store=None,  # nothing configured, so the signer is unknown
    )

    assert result.certificate_id
    assert result.verification_status != "VALID"


# ---------------------------------------------------------------------------
# Residual analysis actually looks for things
# ---------------------------------------------------------------------------


def test_a_surviving_copy_is_found_and_blocks_positive_assurance(
    safe_validator, privileged_client, key_manager, trust_store, temp_dir
):
    """Erasing a named file does not erase its content if a copy survives.

    This is the case path-existence checking cannot see, and the reason the
    content-hash scanner exists. Finding the copy must prevent assurance from
    reaching a clean verdict.
    """
    payload = "the same secret bytes"
    target = temp_dir / "original.txt"
    target.write_text(payload)
    survivor = temp_dir / "backup-copy.txt"
    survivor.write_text(payload)

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        trust_store=trust_store,
    )

    assert not target.exists()
    assert survivor.exists()

    residual = result.outcome(Stage.ANALYZE_RESIDUALS)
    assert "residual finding" in residual.detail
    assert result.assurance_status != AssuranceStatus.PASSED.name


def test_the_recovery_stage_finds_a_surviving_copy(temp_dir):
    """Filesystem enumeration is a real recovery method, and it can succeed."""
    payload = b"recoverable content"
    target = temp_dir / "gone.txt"
    copy = temp_dir / "still-here.txt"
    copy.write_bytes(payload)

    baseline = {"hashes": {"sha256": hashlib.sha256(payload).hexdigest()}}
    report = RecoveryTester().run(baseline, target)

    assert report.data_was_recovered is True
    enumeration = next(
        o for o in report.outcomes if o.method is RecoveryMethod.FILESYSTEM_ENUMERATION
    )
    assert enumeration.recovered is True
    assert str(copy) in enumeration.artifacts


# ---------------------------------------------------------------------------
# The claims the system refuses to make
# ---------------------------------------------------------------------------


def test_recovery_testing_never_claims_universal_irrecoverability(temp_dir):
    """The single most important thing this system must not say.

    A method that found nothing is evidence about that method. The report has no
    field that can express "unrecoverable by any means", and the one that names
    the idea is permanently None.
    """
    target = temp_dir / "absent.txt"
    baseline = {"hashes": {"sha256": hashlib.sha256(b"x").hexdigest()}}
    report = RecoveryTester().run(baseline, target)

    assert report.universal_irrecoverability is None
    assert report.data_was_recovered is False
    assert "establishes that the data is" in report.to_dict()["scope_note"]

    # And the methods that were never attempted are named, not omitted.
    assert {o.method for o in report.not_attempted} >= {
        RecoveryMethod.MFT_RECORD,
        RecoveryMethod.USN_JOURNAL,
        RecoveryMethod.UNALLOCATED_CARVING,
        RecoveryMethod.PHYSICAL_MEDIUM,
    }


def test_an_unattempted_method_cannot_report_a_result():
    """Enforced in the type, not left to callers to remember."""
    with pytest.raises(ValueError, match="must assert nothing"):
        MethodOutcome(
            method=RecoveryMethod.MFT_RECORD,
            state=AnalysisState.UNAVAILABLE,
            recovered=False,
            detail="not attempted",
        )


def test_unattempted_methods_never_strengthen_assurance(temp_dir):
    """An unavailable capability must not quietly count as a passed test."""
    target = temp_dir / "gone.txt"
    baseline = {"hashes": {"sha256": hashlib.sha256(b"x").hexdigest()}}
    report = RecoveryTester().run(baseline, target)

    results = report.to_assurance_results()
    assert {r.test_id for r in results} == {RecoveryMethod.FILESYSTEM_ENUMERATION.value}


def test_a_pipeline_result_always_carries_its_limitations(
    safe_validator, privileged_client, key_manager, trust_store, temp_dir
):
    """The scope of what was and was not done travels with the result."""
    target = temp_dir / "limited.txt"
    target.write_text("payload")

    result = run_pipeline(
        safe_validator,
        privileged_client,
        target,
        key_manager=key_manager,
        trust_store=trust_store,
    )

    joined = " ".join(result.limitations).lower()
    assert "no overwrite" in joined
    assert "raw volume access" in joined


# ---------------------------------------------------------------------------
# Coverage is separate from findings
# ---------------------------------------------------------------------------


def test_residual_coverage_degrades_when_a_scanner_cannot_run(temp_dir):
    """A scan that could not run must not support "nothing was found"."""
    target = temp_dir / "no-baseline-hash.txt"
    target.write_text("payload")

    # No hash in the baseline: the content-copy scanner cannot do its job.
    report = ResidualScanSuite.default().run({"hashes": {}}, target)

    assert report.coverage is not AnalysisState.PERFORMED
    assert any("no SHA-256" in limitation for limitation in report.limitations)


def test_unavailable_capabilities_are_always_reported(temp_dir):
    """Their absence must never be mistaken for a clean result."""
    target = temp_dir / "any.txt"
    target.write_text("payload")

    report = ResidualScanSuite.default().run({"hashes": {"sha256": "00" * 32}}, target)
    joined = " ".join(report.limitations)

    assert "MFT" in joined
    assert "USN journal" in joined
    assert "shadow copy" in joined.lower()
