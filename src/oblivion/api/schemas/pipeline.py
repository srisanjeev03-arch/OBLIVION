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
