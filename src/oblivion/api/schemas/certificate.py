"""Pydantic schemas for certificates and their verification.

The request schema is deliberately tiny. A client may tell the verifier what it
*expects* - which operation and which target it believes the certificate is
about - because that is exactly the independent input the verifier cannot
manufacture for itself. A client may not assert anything about the *outcome*:
there is no field for signer trust, evidence integrity, or the verdict, so no
request can talk the server into a result it did not compute.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    evidence_digest: str
    schema_version: str
    canonicalization_version: str | None = None
    previous_evidence_id: str | None = None
    created_at: datetime


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    evidence_id: str | None = None
    evidence_digest: str
    certificate_version: str
    canonicalization_version: str | None = None
    evidence_schema_version: str | None = None
    target_identity: str | None = None
    method: str | None = None
    result: str | None = None
    signer_id: str | None = None
    signing_algorithm: str
    key_id: str | None = None
    #: The signer's PUBLIC key. The private key exists nowhere in this API.
    public_key: str
    signature: str
    claim: str | None = None
    issued_at: datetime


class CertificateVerificationRequest(BaseModel):
    """Independent expectations the caller brings to the verification.

    Both are optional. Omitting one is honest - the corresponding dimension
    reports ``NOT_CHECKED`` and the overall result becomes ``INCONCLUSIVE``
    rather than pretending the check succeeded.
    """

    model_config = ConfigDict(extra="forbid")

    expected_operation_id: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "The operation the caller believes this certificate attests to. "
            "Compared against the certificate and its evidence."
        ),
    )
    expected_target_identity: str | None = Field(
        default=None,
        max_length=1024,
        description=(
            "The target the caller believes this certificate attests to. "
            "Compared against the certificate and its evidence."
        ),
    )


class DimensionResultOut(BaseModel):
    dimension: str
    result: str = Field(..., pattern="^(PASS|FAIL|NOT_CHECKED|INCONCLUSIVE)$")
    detail: str
    evidence_ref: str | None = None


class CertificateVerificationOut(BaseModel):
    certificate_id: str
    overall_status: str = Field(..., pattern="^(VALID|INVALID|INCONCLUSIVE)$")
    dimensions: list[DimensionResultOut]
    #: Every limitation, named. Never a vague "verification incomplete".
    cannot_prove: list[str] = Field(default_factory=list)
    certificate_version: str | None = None
    verifier_version: str
    verified_at: datetime
    #: Convenience views; null means the question was not answered.
    signature_valid: bool | None = None
    evidence_integrity: bool | None = None
    signer_trusted: bool | None = None
