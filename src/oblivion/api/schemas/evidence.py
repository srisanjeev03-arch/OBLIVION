"""Pydantic schemas for evidence."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaselineCreate(BaseModel):
    operation_id: str
    target_id: str
    file_inventory: dict[str, Any] | None = None
    hashes: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None


class BaselineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    target_id: str
    created_at: datetime


class RecoveryTestCreate(BaseModel):
    operation_id: str
    result_status: str
    evidence_json: dict[str, Any] | None = None


class RecoveryTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    result_status: str
    created_at: datetime


class ResidualFindingCreate(BaseModel):
    operation_id: str
    severity: str = Field(..., max_length=32)
    description: str
    artifact_path: str | None = None
    evidence_json: dict[str, Any] | None = None


class ResidualFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    severity: str
    description: str
    artifact_path: str | None = None
    created_at: datetime


class AssuranceResultCreate(BaseModel):
    operation_id: str
    status: str
    confidence: str
    reasons: list[str] | None = None
    limitations: list[str] | None = None


class AssuranceResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    status: str
    confidence: str
    created_at: datetime
