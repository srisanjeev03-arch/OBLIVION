"""The evidence document: what Oblivion observed, what it did not, and how a
sequence of those documents links together.

Evidence records facts. It does not record conclusions, and it never records a
conclusion the system did not actually reach.

The central distinction is :class:`ObservationState`. A field that is absent, a
scan that could not run and a scan that ran and found nothing are three
different things, and collapsing them is how a system ends up certifying an
operation it never examined. Every observation therefore carries its own state,
and there is no way to express "value present" without also saying how it was
obtained.

Nothing here interprets evidence. Interpretation belongs to the assurance rule
(`core/assurance/rules.py`), which applies the same discipline through
``EvidenceCoverage``.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from .canonicalize import CANONICALIZATION_VERSION, canonical_hash, canonicalize

#: Identifies the evidence document shape. Recorded in every record and checked
#: at verification time, so a future shape change cannot be mistaken for this one.
EVIDENCE_SCHEMA_VERSION = "oblivion-evidence-1"

SUPPORTED_EVIDENCE_SCHEMA_VERSIONS: frozenset[str] = frozenset({EVIDENCE_SCHEMA_VERSION})

#: Substrings that must never appear in an evidence field name. Evidence is
#: signed, persisted and handed to verifiers, so anything secret that reaches it
#: is disclosed permanently and cannot be withdrawn.
FORBIDDEN_FIELD_PATTERNS = (
    "password",
    "passwd",
    "secret",
    "token",
    "bearer",
    "private_key",
    "privatekey",
    "signing_key",
    "vault_key",
    "recovery_key",
    "credential",
    "api_key",
    "apikey",
    "dsn",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(ValueError):
    """Raised when an evidence record cannot be built or is malformed."""


class ObservationState(str, Enum):
    """How a value in the evidence came to be - or why it is absent."""

    #: Oblivion measured this directly.
    OBSERVED = "OBSERVED"
    #: Derived from observations by a documented deterministic rule.
    INFERRED = "INFERRED"
    #: Never attempted in this operation.
    NOT_CHECKED = "NOT_CHECKED"
    #: Attempted, but not obtainable here (unsupported medium, missing
    #: capability, platform limitation, error).
    UNAVAILABLE = "UNAVAILABLE"


#: States that carry a usable value. The other two never do.
_STATES_WITH_VALUE = frozenset({ObservationState.OBSERVED, ObservationState.INFERRED})


@dataclass(frozen=True)
class Observation:
    """One fact, together with how it was obtained.

    A ``NOT_CHECKED`` or ``UNAVAILABLE`` observation cannot carry a value. That
    is enforced rather than documented, because the whole point of the type is
    that a missing measurement can never be read as a present one.
    """

    state: ObservationState
    value: Any = None
    detail: str = ""
    source: str | None = None

    def __post_init__(self) -> None:
        if self.state not in _STATES_WITH_VALUE and self.value is not None:
            raise EvidenceError(
                f"An observation in state {self.state.value} cannot carry a value; "
                "absence of a measurement must not be recorded as one"
            )

    @property
    def has_value(self) -> bool:
        return self.state in _STATES_WITH_VALUE

    # Constructors, named so the call site reads as the claim being made.

    @classmethod
    def observed(cls, value: Any, detail: str = "", source: str | None = None) -> Observation:
        return cls(ObservationState.OBSERVED, value, detail, source)

    @classmethod
    def inferred(cls, value: Any, detail: str, source: str | None = None) -> Observation:
        return cls(ObservationState.INFERRED, value, detail, source)

    @classmethod
    def not_checked(cls, detail: str = "") -> Observation:
        return cls(ObservationState.NOT_CHECKED, None, detail)

    @classmethod
    def unavailable(cls, detail: str) -> Observation:
        return cls(ObservationState.UNAVAILABLE, None, detail)

    def to_canonical(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "value": self.value,
            "detail": self.detail,
            "source": self.source,
        }


@dataclass(frozen=True)
class TargetDescriptor:
    """Identity of what an operation acted on."""

    identity: str
    target_type: str = "unknown"
    volume_serial: str | None = None
    file_id: str | None = None
    filesystem: str | None = None
    #: SHA-256 of the target's content, when it was captured before removal.
    content_digest: str | None = None

    def to_canonical(self) -> dict[str, Any]:
        return {
            "content_digest": self.content_digest,
            "file_id": self.file_id,
            "filesystem": self.filesystem,
            "identity": self.identity,
            "target_type": self.target_type,
            "volume_serial": self.volume_serial,
        }


def _reject_secret_field_names(observations: dict[str, Observation]) -> None:
    for name in observations:
        lowered = name.lower()
        for pattern in FORBIDDEN_FIELD_PATTERNS:
            if pattern in lowered:
                raise EvidenceError(
                    f"Observation name {name!r} matches forbidden pattern "
                    f"{pattern!r}. Evidence is signed and published; secrets "
                    "placed in it cannot be withdrawn."
                )


def new_evidence_id() -> str:
    return f"ev_{uuid.uuid4().hex[:16]}"


@dataclass(frozen=True)
class EvidenceRecord:
    """A signable statement of what was observed during one operation.

    Immutable by construction: the digest is a function of the content, so a
    record that could be edited in place would have a digest that silently
    stopped describing it.
    """

    evidence_id: str
    operation_id: str
    target: TargetDescriptor
    method: str
    observations: dict[str, Observation] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    producer: str = "oblivion"
    producer_version: str = "0.1.0"
    schema_version: str = EVIDENCE_SCHEMA_VERSION
    canonicalization_version: str = CANONICALIZATION_VERSION
    #: Link to the preceding record in this operation's chain, if any.
    previous_evidence_id: str | None = None
    previous_evidence_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise EvidenceError("evidence_id is required")
        if not self.operation_id:
            raise EvidenceError("operation_id is required")
        if not self.target.identity:
            raise EvidenceError("target identity is required")
        _reject_secret_field_names(self.observations)
        if self.previous_evidence_digest is not None and not _HEX64.match(
            self.previous_evidence_digest
        ):
            raise EvidenceError(
                "previous_evidence_digest must be 64 lowercase hex characters"
            )
        # A link is only a link if both halves are present.
        if bool(self.previous_evidence_id) != bool(self.previous_evidence_digest):
            raise EvidenceError(
                "previous_evidence_id and previous_evidence_digest must be set "
                "together; a reference without a digest cannot be verified"
            )

    def to_canonical_dict(self) -> dict[str, Any]:
        """The exact structure that gets canonicalized, hashed and signed."""
        return {
            "canonicalization_version": self.canonicalization_version,
            "created_at": self.created_at.isoformat(),
            "evidence_id": self.evidence_id,
            "limitations": list(self.limitations),
            "method": self.method,
            "observations": {
                name: obs.to_canonical() for name, obs in self.observations.items()
            },
            "operation_id": self.operation_id,
            "previous_evidence_digest": self.previous_evidence_digest,
            "previous_evidence_id": self.previous_evidence_id,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "schema_version": self.schema_version,
            "target": self.target.to_canonical(),
        }

    @classmethod
    def from_canonical_dict(cls, data: dict[str, Any]) -> EvidenceRecord:
        """Rebuild a record from the structure :meth:`to_canonical_dict` produced.

        Round-tripping must preserve the digest exactly: a record loaded from
        storage has to hash to the value the certificate recorded, or every
        verification after a restart would fail for the wrong reason.
        """
        try:
            target_data = data["target"]
            target = TargetDescriptor(
                identity=target_data["identity"],
                target_type=target_data.get("target_type", "unknown"),
                volume_serial=target_data.get("volume_serial"),
                file_id=target_data.get("file_id"),
                filesystem=target_data.get("filesystem"),
                content_digest=target_data.get("content_digest"),
            )
            observations = {
                name: Observation(
                    state=ObservationState(item["state"]),
                    value=item.get("value"),
                    detail=item.get("detail", ""),
                    source=item.get("source"),
                )
                for name, item in data["observations"].items()
            }
            return cls(
                evidence_id=data["evidence_id"],
                operation_id=data["operation_id"],
                target=target,
                method=data["method"],
                observations=observations,
                limitations=tuple(data.get("limitations", ())),
                created_at=datetime.fromisoformat(data["created_at"]),
                producer=data["producer"],
                producer_version=data["producer_version"],
                schema_version=data["schema_version"],
                canonicalization_version=data["canonicalization_version"],
                previous_evidence_id=data.get("previous_evidence_id"),
                previous_evidence_digest=data.get("previous_evidence_digest"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise EvidenceError(
                f"Stored evidence could not be read back ({type(exc).__name__}: {exc})"
            ) from None

    def canonical_bytes(self) -> bytes:
        return canonicalize(self.to_canonical_dict())

    def digest(self) -> str:
        """SHA-256 over the canonical bytes. Changes whenever the content does."""
        return canonical_hash(self.to_canonical_dict())

    def observation(self, name: str) -> Observation:
        """The named observation, or NOT_CHECKED when it was never recorded.

        Absence is reported as absence - never as a value.
        """
        return self.observations.get(
            name, Observation.not_checked(f"No observation named {name!r} was recorded")
        )


# ---------------------------------------------------------------------------
# Chain
# ---------------------------------------------------------------------------
#
# Object integrity and chain integrity are different properties, and conflating
# them is a real failure mode: a record whose own digest is correct says nothing
# whatsoever about whether the records before it are intact, or whether any were
# removed. The verifier below never reports a chain as intact on the strength of
# the final record alone.


class ChainStatus(str, Enum):
    INTACT = "INTACT"
    BROKEN = "BROKEN"
    #: No chain was supplied, so nothing about history could be established.
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class ChainVerification:
    status: ChainStatus
    checked: int
    reason: str
    first_invalid_evidence_id: str | None = None

    @property
    def intact(self) -> bool:
        return self.status is ChainStatus.INTACT


def verify_evidence_chain(records: list[EvidenceRecord]) -> ChainVerification:
    """Verify a chain of evidence records, oldest first.

    Establishes three things, in order:

    1. every record's digest matches its content;
    2. every record after the first names its predecessor;
    3. the digest each record recorded for its predecessor equals that
       predecessor's actual digest.

    An empty sequence is ``UNVERIFIABLE``, never ``INTACT``.

    A single record is ``INTACT`` only when it declares itself the genesis - no
    predecessor reference - because then there is no history for it to be
    missing. A lone record that *does* name a predecessor is ``UNVERIFIABLE``:
    that is the case where someone supplies the newest record alone and its own
    correct digest says nothing about what came before.
    """
    if not records:
        return ChainVerification(
            ChainStatus.UNVERIFIABLE,
            0,
            "No evidence records were supplied, so no chain could be verified.",
        )

    head = records[0]
    if head.previous_evidence_id is not None:
        return ChainVerification(
            ChainStatus.UNVERIFIABLE,
            0,
            (
                f"The earliest record supplied ({head.evidence_id}) references a "
                "predecessor that was not provided, so the chain is incomplete."
            ),
            head.evidence_id,
        )

    previous: EvidenceRecord | None = None
    for index, record in enumerate(records):
        if previous is None:
            if record.previous_evidence_id is not None:
                return ChainVerification(
                    ChainStatus.BROKEN,
                    index + 1,
                    f"Record {record.evidence_id} unexpectedly references a predecessor.",
                    record.evidence_id,
                )
        else:
            if record.previous_evidence_id != previous.evidence_id:
                return ChainVerification(
                    ChainStatus.BROKEN,
                    index + 1,
                    (
                        f"Record {record.evidence_id} names predecessor "
                        f"{record.previous_evidence_id!r}, but the preceding record "
                        f"is {previous.evidence_id!r}."
                    ),
                    record.evidence_id,
                )
            actual = previous.digest()
            if record.previous_evidence_digest != actual:
                return ChainVerification(
                    ChainStatus.BROKEN,
                    index + 1,
                    (
                        f"Record {record.evidence_id} records a predecessor digest "
                        "that does not match the actual digest of "
                        f"{previous.evidence_id}; the earlier record was modified "
                        "or replaced."
                    ),
                    record.evidence_id,
                )
        previous = record

    if len(records) == 1:
        return ChainVerification(
            ChainStatus.INTACT,
            1,
            (
                "A single genesis record with no predecessor: the chain is "
                "complete because there is no earlier history to be missing."
            ),
        )

    return ChainVerification(
        ChainStatus.INTACT,
        len(records),
        f"{len(records)} records form an unbroken chain.",
    )


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "FORBIDDEN_FIELD_PATTERNS",
    "SUPPORTED_EVIDENCE_SCHEMA_VERSIONS",
    "ChainStatus",
    "ChainVerification",
    "EvidenceError",
    "EvidenceRecord",
    "Observation",
    "ObservationState",
    "TargetDescriptor",
    "new_evidence_id",
    "verify_evidence_chain",
]
