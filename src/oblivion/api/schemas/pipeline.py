"""Pydantic schemas for the closed-loop pipeline endpoint.

There is no request body. Everything the pipeline acts on - the target, the
mode, the policy, the approval - is read from the persisted operation record,
and the actor comes from the authenticated session. A client therefore cannot
redirect an approved erasure at a different path, or claim to be someone else,
because there is no field in which to say either thing.

The response uses explicit enums for every state. The frontend must not have to
parse prose to learn what happened.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PipelineStage(str, Enum):
    """The closed loop, in order. Mirrors ``core.pipeline.Stage``."""

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


class PipelineStageStatus(str, Enum):
    """How a stage ended.

    ``SKIPPED`` and ``UNAVAILABLE`` are distinct on the wire for the same reason
    they are distinct internally: chosen not to run, versus tried and could not.
    """

    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    SKIPPED = "SKIPPED"


class AssuranceStatusOut(str, Enum):
    PASSED = "PASSED"
    PARTIAL = "PARTIAL"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"


class VerificationStatusOut(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"


class OperationStateOut(str, Enum):
    """Terminal states an operation can end the pipeline in."""

    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    CANCELLED = "CANCELLED"


class CoverageState(str, Enum):
    """How much of a supported analysis actually ran.

    The distinction between `PARTIAL` and `PERFORMED` is the point: before it
    existed, "one of several recovery methods ran" and "every supported method
    ran" were reported identically, and a client could not tell them apart.
    """

    #: Never attempted.
    NOT_PERFORMED = "NOT_PERFORMED"
    #: Attempted, but nothing this build supports could run here.
    UNAVAILABLE = "UNAVAILABLE"
    #: Ran but reached no determination.
    INCONCLUSIVE = "INCONCLUSIVE"
    #: Ran, but did not cover every method or scanner this build supports.
    PARTIAL = "PARTIAL"
    #: Every supported method or scanner ran. Complete coverage *of what this
    #: build supports* - never a claim that unsupported techniques were applied.
    PERFORMED = "PERFORMED"


class RecoveryMethodCoverageOut(BaseModel):
    """Which recovery methods ran, and what each one did.

    Named lists rather than counts, so a client can render exactly which
    techniques were and were not applied instead of inferring it.
    """

    model_config = ConfigDict(extra="forbid")

    supported: list[str] = Field(
        default_factory=list, description="Methods this build can perform at all."
    )
    attempted: list[str] = Field(default_factory=list)
    successful: list[str] = Field(
        default_factory=list,
        description="Methods that recovered the data. Non-empty means recoverable.",
    )
    failed: list[str] = Field(
        default_factory=list,
        description=(
            "Methods that ran and did not recover the data. Evidence about those "
            "methods only - never evidence of irrecoverability."
        ),
    )
    unavailable: list[str] = Field(
        default_factory=list,
        description="Methods never attempted, because this build cannot perform them.",
    )


class ResidualScannerCoverageOut(BaseModel):
    """Which residual scanners ran."""

    model_config = ConfigDict(extra="forbid")

    supported: list[str] = Field(default_factory=list)
    ran: list[str] = Field(default_factory=list)
    inconclusive: list[str] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)


class CoverageOut(BaseModel):
    """What was actually searched.

    Present so no client ever has to infer coverage from an empty findings list
    or a single boolean.
    """

    model_config = ConfigDict(extra="forbid")

    residual_analysis: CoverageState = CoverageState.NOT_PERFORMED
    recovery_test: CoverageState = CoverageState.NOT_PERFORMED
    recovery_methods: RecoveryMethodCoverageOut = Field(
        default_factory=RecoveryMethodCoverageOut
    )
    residual_scanners: ResidualScannerCoverageOut = Field(
        default_factory=ResidualScannerCoverageOut
    )


class PipelineStageOut(BaseModel):
    """One stage, and what it established."""

    model_config = ConfigDict(extra="forbid")

    stage: PipelineStage
    status: PipelineStageStatus
    detail: str = Field(
        description=(
            "Why the stage ended as it did. Human-readable; never the only "
            "machine-readable signal - use `status`."
        )
    )


class PipelineResultOut(BaseModel):
    """The whole run.

    ``certificate_id`` is null whenever issuance was refused or unavailable, and
    the corresponding stage says why. A null certificate is a normal, meaningful
    outcome - it means nothing certifiable was established - and callers must not
    treat it as an error.
    """

    model_config = ConfigDict(extra="forbid")

    operation_id: str
    target_identity: str
    final_state: OperationStateOut
    stages: list[PipelineStageOut]

    evidence_id: str | None = None
    evidence_digest: str | None = None
    certificate_id: str | None = None

    assurance_status: AssuranceStatusOut | None = None
    verification_status: VerificationStatusOut | None = None

    coverage: CoverageOut = Field(
        default_factory=CoverageOut,
        description=(
            "What was actually searched. Read this alongside `assurance_status`: "
            "PASSED with PARTIAL recovery coverage means no artifacts were found "
            "by the methods that ran, not that every method was tried."
        ),
    )

    limitations: list[str] = Field(
        default_factory=list,
        description=(
            "What this operation did not establish, including recovery methods "
            "that were never attempted and sanitization that was never performed."
        ),
    )

    #: Whether privileged work actually crossed a process boundary. False means
    #: the service ran in the API process - fine for development, and something
    #: a deployment check should be able to see rather than assume.
    privilege_isolated: bool = False
