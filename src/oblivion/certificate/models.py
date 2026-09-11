"""The certificate: a signed statement *about* evidence.

A certificate carries claims. It is not, and must never become, proof of its own
claims. Everything here is therefore designed to be checked against something
outside the certificate:

* ``evidence_digest`` is checked by recomputing the digest of the evidence;
* ``signer_id`` and ``key_id`` are looked up in a TrustStore the *verifier*
  configures;
* ``operation_id`` and ``target_identity`` are compared against expectations the
  *caller* supplies.

The embedded ``public_key`` is a claim about which key signed this, nothing
more. It is deliberately insufficient to establish trust - see
``docs/OBLIVION_DOCUMENTATION.md §21``.

The signature covers the whole canonical payload, not just the evidence digest,
so altering any field above invalidates it.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from oblivion.core.evidence.canonicalize import (
    CANONICALIZATION_VERSION,
    canonicalize,
)
from oblivion.core.evidence.record import EVIDENCE_SCHEMA_VERSION

#: The signed certificate shape introduced by Phase 23.
#:
#: Version 1.0.0 certificates signed only the evidence digest, with a key that
#: was regenerated per process. They are not verifiable by this build and are
#: reported as an unsupported version rather than silently reinterpreted.
CERTIFICATE_VERSION = "2.0.0"

SUPPORTED_CERTIFICATE_VERSIONS: frozenset[str] = frozenset({CERTIFICATE_VERSION})

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def new_certificate_id() -> str:
    return f"cert_{uuid.uuid4().hex[:16]}"


@dataclass(frozen=True)
class Certificate:
    """An issued certificate. Immutable; the signature describes exact content."""

    certificate_id: str
    operation_id: str
    evidence_id: str
    evidence_digest: str
    target_identity: str
    method: str
    result: str
    signer_id: str
    key_id: str
    #: Hex-encoded Ed25519 public key. A *claim* about the signer, not a trust root.
    public_key: str
    #: Hex-encoded Ed25519 signature over :meth:`signing_payload`.
    signature: str
    issued_at: datetime
    version: str = CERTIFICATE_VERSION
    canonicalization_version: str = CANONICALIZATION_VERSION
    evidence_schema_version: str = EVIDENCE_SCHEMA_VERSION
    limitations: tuple[str, ...] = ()

    def signing_payload(self) -> dict[str, Any]:
        """Exactly what the signature covers.

        Every field a verifier relies on is included, so changing any of them -
        the evidence digest, the operation, the target, the declared signer -
        breaks the signature. The signature itself is naturally excluded.
        """
        return {
            "canonicalization_version": self.canonicalization_version,
            "certificate_id": self.certificate_id,
            "certificate_version": self.version,
            "evidence_digest": self.evidence_digest,
            "evidence_id": self.evidence_id,
            "evidence_schema_version": self.evidence_schema_version,
            "issued_at": self.issued_at.isoformat(),
            "key_id": self.key_id,
            "limitations": list(self.limitations),
            "method": self.method,
            "operation_id": self.operation_id,
            "public_key": self.public_key,
            "result": self.result,
            "signer_id": self.signer_id,
            "target_identity": self.target_identity,
        }

    def signing_bytes(self) -> bytes:
        return canonicalize(self.signing_payload())


__all__ = [
    "CERTIFICATE_VERSION",
    "HEX64",
    "SUPPORTED_CERTIFICATE_VERSIONS",
    "Certificate",
    "new_certificate_id",
]
