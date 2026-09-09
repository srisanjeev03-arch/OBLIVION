"""Pydantic schemas for operations."""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class TargetCreate(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024)
    target_type: str = Field(..., pattern="^(file|directory)$")


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    path: str
    canonical_path: str
    target_type: str
    sha256: Optional[str] = None


class OperationCreate(BaseModel):
    target_id: str
    mode: str = Field(..., max_length=64)
    policy_id: Optional[str] = None
    actor_id: Optional[str] = None


class OperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    target_id: str
    mode: str
    state: str
    actor_id: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class OperationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    sequence: int
    event_type: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    created_at: datetime
