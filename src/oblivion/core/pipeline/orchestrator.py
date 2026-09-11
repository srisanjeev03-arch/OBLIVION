"""The closed loop: discover, erase, test, analyse, assess, evidence, certify.

This is the module that makes the rest of the system a product rather than a
collection of capable parts. Before it existed, ``BaselineManager``,
``RecoveryTester``, the residual scanners, ``AssuranceEngine``, the evidence
generator and the certificate issuer all worked and none of them called each
other.

Three rules shape the whole design.

**Every stage records what it did, including nothing.** A stage that was skipped,
refused or unavailable produces an outcome saying so. There is no path where a
stage silently does not happen and the pipeline continues as though it had.

**Later stages cannot invent earlier ones.** Assurance consumes the coverage that
the recovery and residual stages actually reported. If a scan did not run, the
coverage says ``NOT_PERFORMED`` and assurance is inconclusive by construction -
not because this module decided to be cautious, but because the assurance engine
cannot reach a positive verdict without evidence that the analyses ran.

**A certificate requires more than a successful deletion.** Issuance is refused
unless execution actually happened and assurance actually ran. "The delete call
returned success" is not a certifiable fact about recoverability, and the
issuance gate here says so explicitly rather than relying on callers to be
careful.

Destructive work is never performed in this process. Every filesystem mutation
goes through :class:`~oblivion.privileged.client.PrivilegedClient`, so the
privileged boundary re-validates containment, policy and target identity for
itself.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from oblivion.certificate.issuer import CertificateIssuer, IssuanceRequest
from oblivion.certificate.keys import SigningKeyManager
from oblivion.certificate.trust_model import TrustStore
from oblivion.certificate.verification import VerificationContext, verify_certificate
from oblivion.core.assurance.engine import AssuranceEngine
from oblivion.core.assurance.models import (
    AnalysisState,
    AssuranceStatus,
    EvidenceCoverage,
    ResidualFinding,
)
from oblivion.core.baseline.manager import BaselineManager
from oblivion.core.discovery.analyzer import TargetAnalyzer
from oblivion.core.dryrun.planner import DryRunPlanner
from oblivion.core.erasure.engine import MODE_CAPABILITY, ErasureMode
from oblivion.core.evidence.generator import (
    EvidenceGenerationContext,
    EvidenceGenerator,
    Unavailable,
)
from oblivion.core.evidence.record import TargetDescriptor
from oblivion.core.recovery.testing import RecoveryTester
from oblivion.core.residual.scanners import ResidualScanSuite
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.state.machine import State
from oblivion.persistence.repositories.certificate_repo import CertificateRepository
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.privileged.client import PrivilegedClient
from oblivion.privileged.protocol import PrivilegedOperation, ResponseStatus
from oblivion.privileged.transport import ServiceUnavailableError

logger = logging.getLogger(__name__)


class Stage(str, Enum):
    """The closed loop, in order."""

    DISCOVER = "DISCOVER"
    BASELINE = "BASELINE"
    RECOMMEND = "RECOMMEND"
    AUTHORIZE = "AUTHORIZE"
    ERASE = "ERASE"
    VALIDATE = "VALIDATE"
    TEST_RECOVERY = "TEST_RECOVERY"
    ANALYZE_RESIDUALS = "ANALYZE_RESIDUALS"
    ASSESS_ASSURANCE = "ASSESS_ASSURANCE"
    GENERATE_EVIDENCE = "GENERATE_EVIDENCE"
    ISSUE_CERTIFICATE = "ISSUE_CERTIFICATE"
    VERIFY_CERTIFICATE = "VERIFY_CERTIFICATE"


class StageStatus(str, Enum):
    """How a stage ended.

    ``SKIPPED`` and ``UNAVAILABLE`` are distinct: skipped means the pipeline
    chose not to run it because an earlier stage made it meaningless, while
    unavailable means it was due to run and could not. Assurance treats them
    differently, so collapsing them would lose real information.
    """

    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class StageOutcome:
    """What one stage did."""

    stage: Stage
    status: StageStatus
    detail: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status is StageStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PipelineRequest:
    """One operation through the loop.

    ``actor_id`` must come from the authenticated session. The pipeline does not
    accept it from a request body, and the authorization stage checks the
    persisted operation rather than trusting it.
    """

    operation_id: str
    target_path: str
    target_type: str
    mode: str
    policy_id: str
    actor_id: str
    filesystem: str = "NTFS"


@dataclass
class PipelineResult:
    """Everything the loop established, stage by stage."""

    operation_id: str
    target_identity: str
    stages: list[StageOutcome] = field(default_factory=list)
    evidence_id: str | None = None
    evidence_digest: str | None = None
    certificate_id: str | None = None
    assurance_status: str | None = None
    verification_status: str | None = None
    limitations: list[str] = field(default_factory=list)
    final_state: str = State.CREATED.name

    #: What was actually searched, per analysis and per method/scanner.
    #:
    #: Carried explicitly so a client never has to infer coverage from an empty
    #: findings list or a single boolean - which is what audit finding M-2 was
    #: about. Empty only when the pipeline stopped before coverage was computed.
    coverage: dict[str, Any] = field(default_factory=dict)

    def outcome(self, stage: Stage) -> StageOutcome | None:
        for entry in self.stages:
            if entry.stage is stage:
                return entry
        return None

    @property
    def completed_stages(self) -> list[Stage]:
        return [s.stage for s in self.stages if s.ok]

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "target_identity": self.target_identity,
            "final_state": self.final_state,
            "stages": [s.to_dict() for s in self.stages],
            "evidence_id": self.evidence_id,
            "evidence_digest": self.evidence_digest,
            "certificate_id": self.certificate_id,
            "assurance_status": self.assurance_status,
            "verification_status": self.verification_status,
            "limitations": list(self.limitations),
            "coverage": dict(self.coverage),
        }


#: Which privileged operation performs each mode's destructive step.
_MODE_OPERATION: dict[str, PrivilegedOperation] = {
    "SELECTIVE_PERMANENT": PrivilegedOperation.DELETE_FILE,
    "COMPLETE_ERASURE": PrivilegedOperation.DELETE_TREE,
    "CONTROLLED_RECOVERABLE": PrivilegedOperation.PREPARE_RECOVERY_OBJECT,
}

_MODE_ENUM: dict[str, ErasureMode] = {
    "SELECTIVE_PERMANENT": ErasureMode.SELECTIVE_PERMANENT,
    "COMPLETE_ERASURE": ErasureMode.COMPLETE_ERASURE,
    "CONTROLLED_RECOVERABLE": ErasureMode.CONTROLLED_RECOVERABLE,
}

#: Assurance outcome to the certificate's machine-readable result. INCONCLUSIVE
#: and PARTIAL stay themselves - a certificate that rounded them up to COMPLETED
#: would be the exact fabrication this system exists to avoid.
_RESULT_FOR_ASSURANCE: dict[AssuranceStatus, str] = {
    AssuranceStatus.PASSED: "COMPLETED",
    AssuranceStatus.PARTIAL: "PARTIAL",
    AssuranceStatus.INCONCLUSIVE: "INCONCLUSIVE",
    AssuranceStatus.FAILED: "FAILED",
}


class ClosedLoopPipeline:
    """Runs one operation from discovery through independent verification."""

    def __init__(
        self,
        session: Session,
        validator: SafePathValidator,
        privileged: PrivilegedClient,
        key_manager: SigningKeyManager | None = None,
        trust_store: TrustStore | None = None,
        signer_id: str = "oblivion-issuer",
    ) -> None:
        self._session = session
        self._validator = validator
        self._privileged = privileged
        self._key_manager = key_manager
        self._trust_store = trust_store
        self._signer_id = signer_id

        # The baseline analyser must use *this* pipeline's validator. Left to
        # its default, BaselineManager builds a TargetAnalyzer with a fresh
        # SafePathValidator whose allowed roots are the process temp directory,
        # and every real target is then refused as out of scope.
        self._baseline = BaselineManager(TargetAnalyzer(validator))
        self._recovery = RecoveryTester()
        self._residual = ResidualScanSuite.default()
        self._assurance = AssuranceEngine()
        self._evidence = EvidenceGenerator()

    # -- the loop --------------------------------------------------------

    def run(self, request: PipelineRequest) -> PipelineResult:
        """Run the whole loop, recording every stage."""
        started_at = datetime.now(UTC)
        result = PipelineResult(
            operation_id=request.operation_id, target_identity=request.target_path
        )
        target_path = Path(request.target_path)

        self._discover(request, result)
        baseline = self._capture_baseline(request, result)
        self._recommend(request, result)

        if not self._authorize(request, result):
            # Nothing destructive has happened, and nothing is going to. The
            # operation stops here with a recorded reason rather than falling
            # through to execution.
            result.final_state = State.FAILED.name
            self._finalise_without_certificate(request, result, baseline, started_at)
            return result

        execution = self._erase(request, result)
        verification = self._validate(request, result, target_path, execution)
        recovery_report = self._test_recovery(request, result, baseline, target_path)
        residual_report = self._analyse_residuals(request, result, baseline, target_path)

        coverage = EvidenceCoverage(
            residual_analysis=(
                residual_report.coverage
                if residual_report is not None
                else AnalysisState.NOT_PERFORMED
            ),
            recovery_test=(
                recovery_report.coverage
                if recovery_report is not None
                else AnalysisState.NOT_PERFORMED
            ),
        )

        # Record what was actually searched, not merely that something was.
        result.coverage = {
            "residual_analysis": coverage.residual_analysis.name,
            "recovery_test": coverage.recovery_test.name,
            "recovery_methods": (
                recovery_report.method_coverage
                if recovery_report is not None
                else {}
            ),
            "residual_scanners": (
                residual_report.scanner_coverage
                if residual_report is not None
                else {}
            ),
        }

        assurance = self._assess(
            request, result, coverage, recovery_report, residual_report
        )

        evidence_record = self._generate_evidence(
            request,
            result,
            baseline=baseline,
            execution=execution,
            verification=verification,
            recovery=recovery_report,
            residual=residual_report,
            assurance=assurance,
            started_at=started_at,
        )

        certificate = self._issue_certificate(
            request, result, evidence_record, execution, assurance
        )
        if certificate is not None:
            self._verify_certificate(request, result, certificate, evidence_record)

        result.final_state = self._final_state(result, execution, assurance)
        self._persist_state(request, result)
        return result

    # -- stages ----------------------------------------------------------

    def _discover(
        self, request: PipelineRequest, result: PipelineResult
    ) -> dict[str, Any] | None:
        """Inspect the target through the privileged boundary."""
        try:
            response = self._privileged.inspect_target(
                operation_id=request.operation_id,
                policy_id=request.policy_id,
                mode=request.mode,
                target_path=request.target_path,
                target_type=request.target_type,
                actor_id=request.actor_id,
            )
        except ServiceUnavailableError as exc:
            result.stages.append(
                StageOutcome(
                    Stage.DISCOVER,
                    StageStatus.UNAVAILABLE,
                    f"The privileged service could not be reached: {exc}",
                )
            )
            return None

        if response.status is not ResponseStatus.COMPLETED:
            result.stages.append(
                StageOutcome(
                    Stage.DISCOVER,
                    StageStatus.REFUSED if response.refused else StageStatus.FAILED,
                    "; ".join(response.refusals) or response.message,
                )
            )
            return None

        analysis = response.result.get("analysis")
        result.stages.append(
            StageOutcome(
                Stage.DISCOVER,
                StageStatus.COMPLETED,
                "Target inspected through the privileged boundary.",
                {"analysis": analysis},
            )
        )
        return analysis

    def _capture_baseline(
        self, request: PipelineRequest, result: PipelineResult
    ) -> dict[str, Any] | None:
        """Record the pre-operation state. Must happen before anything destructive."""
        limitations: list[str] = []
        if request.mode in _MODE_ENUM:
            limitations = list(MODE_CAPABILITY[_MODE_ENUM[request.mode]].limitations)

        try:
            baseline = self._baseline.capture_baseline(
                request.target_path,
                scope=request.target_type,
                limitations=limitations,
            )
        except Exception as exc:  # noqa: BLE001 - reported, never raised at a stage
            result.stages.append(
                StageOutcome(
                    Stage.BASELINE,
                    StageStatus.FAILED,
                    f"Baseline capture failed: {type(exc).__name__}: {exc}",
                )
            )
            return None

        result.limitations.extend(limitations)
        result.stages.append(
            StageOutcome(
                Stage.BASELINE,
                StageStatus.COMPLETED,
                "Pre-operation state captured, including the target's SHA-256.",
                {"baseline": baseline},
            )
        )
        return baseline

    def _recommend(self, request: PipelineRequest, result: PipelineResult) -> None:
        """Plan the operation without authorizing or executing it."""
        try:
            plan = DryRunPlanner(
                target=request.target_path,
                scope=request.target_type,
                policy_id=request.policy_id,
                validator=self._validator,
            ).plan()
        except Exception as exc:  # noqa: BLE001
            result.stages.append(
                StageOutcome(
                    Stage.RECOMMEND,
                    StageStatus.FAILED,
                    f"Planning failed: {type(exc).__name__}: {exc}",
                )
            )
            return

        result.limitations.extend(plan.limitations)
        result.stages.append(
            StageOutcome(
                Stage.RECOMMEND,
                StageStatus.COMPLETED,
                (
                    f"Dry run planned the operation. would_proceed="
                    f"{plan.would_proceed}. A plan grants no authorization."
                ),
                {
                    "would_proceed": plan.would_proceed,
                    "authorization": plan.authorization,
                    "warnings": plan.warnings,
                },
            )
        )

    def _authorize(self, request: PipelineRequest, result: PipelineResult) -> bool:
        """Confirm a *durable* approval exists, by someone other than the requester.

        The check reads the persisted operation. Nothing the caller passes can
        satisfy it: an operation that was never approved, or approved by its own
        requester, does not execute.
        """
        operation = OperationRepository(self._session).get_operation(
            request.operation_id
        )

        if operation is None:
            result.stages.append(
                StageOutcome(
                    Stage.AUTHORIZE,
                    StageStatus.REFUSED,
                    "No persisted operation record exists, so no durable "
                    "authorization exists either.",
                )
            )
            return False

        if operation.state != State.READY.name:
            result.stages.append(
                StageOutcome(
                    Stage.AUTHORIZE,
                    StageStatus.REFUSED,
                    f"Operation is in state {operation.state}; only READY "
                    "operations have been approved for execution.",
                )
            )
            return False

        if not operation.approved_by:
            result.stages.append(
                StageOutcome(
                    Stage.AUTHORIZE,
                    StageStatus.REFUSED,
                    "The operation records no approver.",
                )
            )
            return False

        if operation.approved_by == operation.requested_by:
            result.stages.append(
                StageOutcome(
                    Stage.AUTHORIZE,
                    StageStatus.REFUSED,
                    "Separation of duties: the approver is the requester.",
                )
            )
            return False

        result.stages.append(
            StageOutcome(
                Stage.AUTHORIZE,
                StageStatus.COMPLETED,
                "A durable approval by a second actor is recorded.",
                {"approved_by": operation.approved_by},
            )
        )
        return True

    def _erase(
        self, request: PipelineRequest, result: PipelineResult
    ) -> dict[str, Any] | None:
        """Perform the destructive step through the privileged boundary."""
        operation = _MODE_OPERATION.get(request.mode)
        if operation is None:
            result.stages.append(
                StageOutcome(
                    Stage.ERASE,
                    StageStatus.REFUSED,
                    f"Mode {request.mode!r} has no privileged operation mapping.",
                )
            )
            return None

        serial = self._validator.get_volume_serial(request.target_path)
        file_id = self._validator._get_file_id(request.target_path)

        try:
            response = self._privileged.request(
                operation,
                operation_id=request.operation_id,
                policy_id=request.policy_id,
                mode=request.mode,
                target_path=request.target_path,
                target_type=request.target_type,
                actor_id=request.actor_id,
                expected_volume_serial=serial,
                expected_file_id=file_id,
            )
        except ServiceUnavailableError as exc:
            result.stages.append(
                StageOutcome(
                    Stage.ERASE,
                    StageStatus.UNAVAILABLE,
                    f"The privileged service could not be reached: {exc}",
                )
            )
            return None

        if response.status is not ResponseStatus.COMPLETED:
            result.stages.append(
                StageOutcome(
                    Stage.ERASE,
                    StageStatus.REFUSED if response.refused else StageStatus.FAILED,
                    "; ".join(response.refusals) or response.message,
                )
            )
            return None

        result.stages.append(
            StageOutcome(
                Stage.ERASE,
                StageStatus.COMPLETED,
                f"{operation.value} performed by the privileged service.",
                {"execution": response.result},
            )
        )
        return response.result

    # Several stage methods take `request` without reading it. Every stage keeps
    # the same shape so the sequence in `run` reads as one list of steps rather
    # than a set of special cases; the uniformity is worth an unused parameter.

    def _validate(
        self,
        request: PipelineRequest,  # noqa: ARG002 - uniform stage signature
        result: PipelineResult,
        target_path: Path,
        execution: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Check the post-operation filesystem state directly.

        Deliberately re-observes rather than trusting the execution result. The
        engine reporting success and the target actually being gone are two
        different facts, and only the second one is evidence.
        """
        if execution is None:
            result.stages.append(
                StageOutcome(
                    Stage.VALIDATE,
                    StageStatus.SKIPPED,
                    "No execution took place, so there is no post-state to validate.",
                )
            )
            return None

        try:
            present = os.path.lexists(target_path)
        except OSError as exc:
            result.stages.append(
                StageOutcome(
                    Stage.VALIDATE,
                    StageStatus.UNAVAILABLE,
                    f"Post-state could not be read: {exc}",
                )
            )
            return None

        verification = {
            "target_absent": not present,
            "method": "direct filesystem observation after execution",
        }
        result.stages.append(
            StageOutcome(
                Stage.VALIDATE,
                StageStatus.COMPLETED,
                "Target is absent from its path."
                if not present
                else "Target is still present after execution.",
                {"verification": verification},
            )
        )
        return verification

    def _test_recovery(
        self,
        request: PipelineRequest,  # noqa: ARG002 - uniform stage signature
        result: PipelineResult,
        baseline: dict[str, Any] | None,
        target_path: Path,
    ) -> Any:
        """Attempt the recovery methods this build can perform."""
        if baseline is None:
            result.stages.append(
                StageOutcome(
                    Stage.TEST_RECOVERY,
                    StageStatus.UNAVAILABLE,
                    "No baseline was captured, so recovered content could not be "
                    "compared against anything.",
                )
            )
            return None

        report = self._recovery.run(baseline, target_path)
        result.limitations.extend(
            f"Recovery method not attempted: {o.method.value} - {o.detail}"
            for o in report.not_attempted
        )
        result.stages.append(
            StageOutcome(
                Stage.TEST_RECOVERY,
                StageStatus.COMPLETED
                if report.coverage is AnalysisState.PERFORMED
                else StageStatus.UNAVAILABLE,
                (
                    f"{len(report.attempted)} method(s) attempted, "
                    f"{len(report.not_attempted)} not available. "
                    "No result here establishes universal irrecoverability."
                ),
                {"recovery": report.to_dict()},
            )
        )
        return report

    def _analyse_residuals(
        self,
        request: PipelineRequest,  # noqa: ARG002 - uniform stage signature
        result: PipelineResult,
        baseline: dict[str, Any] | None,
        target_path: Path,
    ) -> Any:
        """Search for traces the operation left behind."""
        if baseline is None:
            result.stages.append(
                StageOutcome(
                    Stage.ANALYZE_RESIDUALS,
                    StageStatus.UNAVAILABLE,
                    "No baseline was captured, so residual analysis had nothing to "
                    "compare against.",
                )
            )
            return None

        report = self._residual.run(baseline, target_path)
        result.limitations.extend(report.limitations)
        result.stages.append(
            StageOutcome(
                Stage.ANALYZE_RESIDUALS,
                StageStatus.COMPLETED
                if report.coverage is AnalysisState.PERFORMED
                else StageStatus.UNAVAILABLE,
                (
                    f"{len(report.positive_findings)} residual finding(s); "
                    f"coverage {report.coverage.name}."
                ),
                {"residual": report.to_dict()},
            )
        )
        return report

    def _assess(
        self,
        request: PipelineRequest,
        result: PipelineResult,
        coverage: EvidenceCoverage,
        recovery_report: Any,
        residual_report: Any,
    ) -> Any:
        """Assess assurance from what the earlier stages actually produced."""
        findings: list[ResidualFinding] = []
        if residual_report is not None:
            findings = [
                ResidualFinding(
                    artifact_path=e.artifact_path or "",
                    finding_type=e.evidence_type.name,
                    severity=e.confidence.name,
                    explanation=e.explanation,
                )
                for e in residual_report.positive_findings
            ]

        recovery_results = (
            recovery_report.to_assurance_results()
            if recovery_report is not None
            else []
        )

        assurance = self._assurance.assess(
            operation_id=request.operation_id,
            target_id=request.target_path,
            residual_findings=findings,
            recovery_results=recovery_results,
            coverage=coverage,
            metadata={"mode": request.mode, "policy_id": request.policy_id},
        )

        result.assurance_status = assurance.status.name
        result.stages.append(
            StageOutcome(
                Stage.ASSESS_ASSURANCE,
                StageStatus.COMPLETED,
                f"{assurance.status.name} / {assurance.confidence.name}: "
                f"{assurance.summary}",
                {"assurance": assurance.status.name},
            )
        )
        return assurance

    def _generate_evidence(
        self,
        request: PipelineRequest,
        result: PipelineResult,
        *,
        baseline: Any,
        execution: Any,
        verification: Any,
        recovery: Any,
        residual: Any,
        assurance: Any,
        started_at: datetime,
    ) -> Any:
        """Build and persist the evidence record for this operation."""
        context = EvidenceGenerationContext(
            operation_id=request.operation_id,
            target=TargetDescriptor(
                identity=request.target_path,
                target_type=request.target_type,
                filesystem=request.filesystem,
            ),
            method=request.mode,
            policy_id=request.policy_id,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            baseline=baseline
            if baseline is not None
            else Unavailable("Baseline capture did not succeed for this operation."),
            execution_result=execution
            if execution is not None
            else Unavailable("No execution took place."),
            verification_result=verification
            if verification is not None
            else Unavailable("Post-state was not established."),
            recovery_test_result=recovery.to_dict()
            if recovery is not None
            else Unavailable("Recovery testing did not run."),
            residual_result=residual.to_dict()
            if residual is not None
            else Unavailable("Residual analysis did not run."),
            assurance_result={
                "status": assurance.status.name,
                "confidence": assurance.confidence.name,
                "summary": assurance.summary,
            }
            if assurance is not None
            else Unavailable("Assurance did not run."),
            limitations=tuple(dict.fromkeys(result.limitations)),
        )

        try:
            record = self._evidence.generate(context)
            CertificateRepository(self._session).save_evidence(record)
        except Exception as exc:  # noqa: BLE001
            result.stages.append(
                StageOutcome(
                    Stage.GENERATE_EVIDENCE,
                    StageStatus.FAILED,
                    f"Evidence generation failed: {type(exc).__name__}: {exc}",
                )
            )
            return None

        result.evidence_id = record.evidence_id
        result.evidence_digest = record.digest()
        result.stages.append(
            StageOutcome(
                Stage.GENERATE_EVIDENCE,
                StageStatus.COMPLETED,
                "Evidence generated from observed stage results and persisted.",
                {"evidence_id": record.evidence_id},
            )
        )
        return record

    def _issue_certificate(
        self,
        request: PipelineRequest,  # noqa: ARG002 - uniform stage signature
        result: PipelineResult,
        evidence_record: Any,
        execution: Any,
        assurance: Any,
    ) -> Any:
        """Issue a certificate, or refuse and say why.

        The gate is deliberately strict. A certificate is a statement about what
        was established, so it requires: a signing identity, an evidence record,
        an execution that actually happened, and an assurance assessment that
        actually ran. A successful delete call satisfies none of those on its
        own.
        """
        if self._key_manager is None:
            result.stages.append(
                StageOutcome(
                    Stage.ISSUE_CERTIFICATE,
                    StageStatus.UNAVAILABLE,
                    "No signing identity is configured, so no certificate can be "
                    "issued. An unsigned certificate would be worthless.",
                )
            )
            return None

        missing: list[str] = []
        if evidence_record is None:
            missing.append("evidence record")
        if execution is None:
            missing.append("an execution result")
        if assurance is None:
            missing.append("an assurance assessment")

        if missing:
            result.stages.append(
                StageOutcome(
                    Stage.ISSUE_CERTIFICATE,
                    StageStatus.REFUSED,
                    "Issuance refused: mandatory evidence is unavailable ("
                    + ", ".join(missing)
                    + "). A certificate is never issued merely because a deletion "
                    "returned successfully.",
                )
            )
            return None

        try:
            certificate = CertificateIssuer(self._key_manager, self._signer_id).issue(
                IssuanceRequest(
                    evidence=evidence_record,
                    result=_RESULT_FOR_ASSURANCE.get(assurance.status, "INCONCLUSIVE"),
                    limitations=tuple(dict.fromkeys(result.limitations)),
                )
            )
            CertificateRepository(self._session).save_certificate(certificate)
        except Exception as exc:  # noqa: BLE001
            result.stages.append(
                StageOutcome(
                    Stage.ISSUE_CERTIFICATE,
                    StageStatus.FAILED,
                    f"Issuance failed: {type(exc).__name__}: {exc}",
                )
            )
            return None

        result.certificate_id = certificate.certificate_id
        result.stages.append(
            StageOutcome(
                Stage.ISSUE_CERTIFICATE,
                StageStatus.COMPLETED,
                f"Certificate issued recording result "
                f"{_RESULT_FOR_ASSURANCE.get(assurance.status)!r}.",
                {"certificate_id": certificate.certificate_id},
            )
        )
        return certificate

    def _verify_certificate(
        self,
        request: PipelineRequest,
        result: PipelineResult,
        certificate: Any,
        evidence_record: Any,
    ) -> None:
        """Verify the certificate the way an independent party would.

        The expectations come from the pipeline request rather than off the
        certificate, because a certificate that supplies the facts it is checked
        against proves nothing.
        """
        default_context = VerificationContext()

        # The chain is loaded from storage rather than taken from memory: an
        # independent verifier has only what was persisted, and verifying
        # against the in-memory record would skip the round trip that a real
        # verification depends on.
        chain = tuple(
            CertificateRepository(self._session).load_evidence_chain(
                request.operation_id
            )
        )

        context = VerificationContext(
            trust_store=self._trust_store
            if self._trust_store is not None
            else default_context.trust_store,
            evidence=evidence_record,
            evidence_chain=chain,
            expected_operation_id=request.operation_id,
            expected_target_identity=request.target_path,
        )
        verification = verify_certificate(certificate, context)
        result.verification_status = verification.overall_status
        result.stages.append(
            StageOutcome(
                Stage.VERIFY_CERTIFICATE,
                StageStatus.COMPLETED,
                f"Independent verification: {verification.overall_status}.",
                {"verification": verification.overall_status},
            )
        )

    # -- helpers ---------------------------------------------------------

    def _finalise_without_certificate(
        self,
        request: PipelineRequest,
        result: PipelineResult,
        baseline: Any,
        started_at: datetime,
    ) -> None:
        """Record evidence for an operation that never executed.

        A refused operation is still a fact worth recording: it says the system
        declined, when, and why. The evidence names every stage that did not run
        rather than leaving them absent.
        """
        for stage in (
            Stage.ERASE,
            Stage.VALIDATE,
            Stage.TEST_RECOVERY,
            Stage.ANALYZE_RESIDUALS,
            Stage.ASSESS_ASSURANCE,
        ):
            result.stages.append(
                StageOutcome(
                    stage,
                    StageStatus.SKIPPED,
                    "The operation was not authorized, so this stage did not run.",
                )
            )

        self._generate_evidence(
            request,
            result,
            baseline=baseline,
            execution=None,
            verification=None,
            recovery=None,
            residual=None,
            assurance=None,
            started_at=started_at,
        )
        result.stages.append(
            StageOutcome(
                Stage.ISSUE_CERTIFICATE,
                StageStatus.REFUSED,
                "No execution and no assurance, so nothing may be certified.",
            )
        )
        self._persist_state(request, result)

    def _final_state(
        self, result: PipelineResult, execution: Any, assurance: Any
    ) -> str:
        if execution is None:
            return State.FAILED.name
        if result.certificate_id is None:
            return State.PARTIAL.name
        if assurance is not None and assurance.status is AssuranceStatus.INCONCLUSIVE:
            return State.INCONCLUSIVE.name
        return State.COMPLETED.name

    def _persist_state(self, request: PipelineRequest, result: PipelineResult) -> None:
        operation = OperationRepository(self._session).get_operation(
            request.operation_id
        )
        if operation is not None:
            operation.state = result.final_state
