"""Pydantic schemas for operations."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TargetCreate(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024)
    target_type: str = Field(..., pattern="^(file|directory)$")


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    path: str
    canonical_path: str
    target_type: str
    sha256: str | None = None


class ConfirmationInput(BaseModel):
    acknowledged_risk: bool = Field(..., description="Must explicitly acknowledge destructive operation risk")


class RecoveryConfig(BaseModel):
    retention_seconds: int | None = Field(default=86400, ge=0)


class CreateOperationRequest(BaseModel):
    target_id: str = Field(..., min_length=1)
    mode: str = Field(..., pattern="^(COMPLETE_ERASURE|SELECTIVE_PERMANENT|CONTROLLED_RECOVERABLE)$")
    policy_id: str = Field(default="ERASURE.LOGICAL.SELECTIVE.V1")
    confirmation: ConfirmationInput
    recovery: RecoveryConfig | None = None


class OperationCreate(BaseModel):
    target_id: str
    mode: str = Field(..., max_length=64)
    policy_id: str | None = None
    actor_id: str | None = None


class OperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    target_id: str
    mode: str
    state: str
    policy_id: str | None = None
    progress_percent: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    actor_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class OperationPageOut(BaseModel):
    """A page of persisted operations, newest first.

    ``total`` is the number of operations matching the filter, not the size of
    this page, so a reader can tell a window from the whole set without
    inferring it from the page happening to be full.

    Every row comes from the database. No identifier and no state is
    synthesised here; an operation that does not exist simply does not appear.
    """

    operations: list[OperationOut]
    returned: int
    total: int
    limit: int
    offset: int


class OperationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    sequence: int
    event_type: str
    from_state: str | None = None
    to_state: str | None = None
    payload: str | None = None
    created_at: datetime

