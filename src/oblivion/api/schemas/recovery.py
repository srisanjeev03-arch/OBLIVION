"""Recovery schemas."""

from pydantic import BaseModel, ConfigDict, Field


class RecoveryObjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    status: str = "SEALED"
    original_sha256: str
    original_size: int | None = None
    created_at: str | None = None
    expires_at: str | None = None


class RestoreRequest(BaseModel):
    destination: str = Field(..., min_length=1, max_length=1024)
    allow_overwrite: bool = Field(default=False, description="Explicit consent flag required to overwrite an existing destination file")



class RestoreResponse(BaseModel):
    status: str
    destination: str
    sha256: str
    integrity_verified: bool
