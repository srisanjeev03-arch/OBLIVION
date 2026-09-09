"""Target schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StorageProfile(BaseModel):
    volume: str = "UNKNOWN"
    filesystem: str = "UNKNOWN"
    media_type: str = "UNKNOWN"
    encryption_status: str = "UNKNOWN"
    size_bytes: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Sensitivity(BaseModel):
    level: str = "PUBLIC"  # PUBLIC, INTERNAL, CONFIDENTIAL, CRITICAL
    categories: list[str] = Field(default_factory=list)
    explanation: str = "Advisory classification"


class TargetAnalyzeRequest(BaseModel):
    """Request to analyze a target."""
    path: str = Field(..., min_length=1, max_length=1024)
    include_content_analysis: bool = False


class TargetProfile(BaseModel):
    """Profile of analyzed target."""
    id: str
    path: str
    canonical_path: str | None = None
    type: str  # file, directory
    size_bytes: int = 0
    file_count: int = 0
    sha256: str | None = None
    storage_profile: dict[str, Any] = Field(default_factory=dict)
    sensitivity: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TargetCreate(BaseModel):
    path: str = Field(..., min_length=1, max_length=1024)
    target_type: str = Field(..., pattern="^(file|directory)$")


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    path: str
    canonical_path: str
    target_type: str
    file_count: int | None = None
    total_size: int | None = None
    sha256: str | None = None
    discovered_at: datetime
