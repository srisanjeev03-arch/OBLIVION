"""Issuing a certificate for a piece of evidence.

This is the path that did not exist: ``create_certificate`` sat in the
persistence layer with no caller, so certificates could be verified but never
produced. Issuance is a service rather than a route because Phase 25 is what
connects it to the operation lifecycle; wiring it into a route now would mean
inventing a caller before there is a pipeline to call it.

Issuance is deliberately narrow. It signs what the evidence already says. It
does not evaluate the evidence, does not decide whether an operation succeeded,
and cannot upgrade a partial result into a confident one - the claim it records
is copied from the evidence, never inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from oblivion.core.evidence.record import EvidenceRecord, ObservationState

from .keys import SigningKeyManager
from .models import CERTIFICATE_VERSION, Certificate, new_certificate_id

#: Identity recorded as the signer. A label the TrustStore is keyed by - it
#: confers nothing by itself.
DEFAULT_SIGNER_ID = "oblivion-issuer"


class CertificateIssuanceError(Exception):
    """Raised when a certificate cannot be issued. Never partially issues."""


@dataclass(frozen=True)
class IssuanceRequest:
    """What the caller is asking to certify."""

    evidence: EvidenceRecord
    #: Short machine-readable outcome, e.g. ``"COMPLETED"``. Copied verbatim.
    result: str
    limitations: tuple[str, ...] = ()


class CertificateIssuer:
    """Signs certificates with a configured, persistent identity."""

    def __init__(
        self,
        key_manager: SigningKeyManager,
        signer_id: str = DEFAULT_SIGNER_ID,
    ):
        if not signer_id:
            raise CertificateIssuanceError("signer_id must be non-empty")
        self._key_manager = key_manager
        self._signer_id = signer_id

    @property
    def signer_id(self) -> str:
        return self._signer_id

    @property
    def key_id(self) -> str:
        return self._key_manager.key_id

    def issue(self, request: IssuanceRequest) -> Certificate:
        """Produce a signed certificate for ``request.evidence``.

        The evidence digest is recomputed here rather than accepted from the
        caller: a certificate that attested to a digest nobody checked would
        certify whatever it was handed.
        """
        evidence = request.evidence
        if not request.result:
            raise CertificateIssuanceError("result must be non-empty")

        # The limitations recorded on the evidence travel with the certificate.
        # A verifier reading only the certificate must still see the caveats.
        limitations = tuple(request.limitations) + tuple(evidence.limitations)
        limitations += tuple(self._coverage_limitations(evidence))

        certificate_id = new_certificate_id()
        issued_at = datetime.now(UTC)

        unsigned = Certificate(
            certificate_id=certificate_id,
            operation_id=evidence.operation_id,
            evidence_id=evidence.evidence_id,
            evidence_digest=evidence.digest(),
            target_identity=evidence.target.identity,
            method=evidence.method,
            result=request.result,
            signer_id=self._signer_id,
            key_id=self._key_manager.key_id,
            public_key=self._key_manager.public_key_bytes().hex(),
            signature="",
            issued_at=issued_at,
            version=CERTIFICATE_VERSION,
            canonicalization_version=evidence.canonicalization_version,
            evidence_schema_version=evidence.schema_version,
            limitations=limitations,
        )

        signature = self._key_manager.signer().sign(unsigned.signing_bytes())

        # Rebuilt rather than mutated: Certificate is frozen precisely so a
        # signed object cannot drift from what was signed.
        return Certificate(
            certificate_id=unsigned.certificate_id,
            operation_id=unsigned.operation_id,
            evidence_id=unsigned.evidence_id,
            evidence_digest=unsigned.evidence_digest,
            target_identity=unsigned.target_identity,
            method=unsigned.method,
            result=unsigned.result,
            signer_id=unsigned.signer_id,
            key_id=unsigned.key_id,
            public_key=unsigned.public_key,
            signature=signature.hex(),
            issued_at=unsigned.issued_at,
            version=unsigned.version,
            canonicalization_version=unsigned.canonicalization_version,
            evidence_schema_version=unsigned.evidence_schema_version,
            limitations=unsigned.limitations,
        )

    @staticmethod
    def _coverage_limitations(evidence: EvidenceRecord) -> list[str]:
        """Name every lifecycle stage the evidence says was not established.

        Without this a certificate could look complete simply because the
        stages that never ran are invisible in it.
        """
        absent = [
            name
            for name in ("recovery_test", "residual_analysis", "assurance")
            if evidence.observation(name).state
            in (ObservationState.NOT_CHECKED, ObservationState.UNAVAILABLE)
        ]
        if not absent:
            return []
        return [
            "This certificate attests only to what the evidence records. "
            f"Not established: {', '.join(sorted(absent))}."
        ]


__all__ = [
    "DEFAULT_SIGNER_ID",
    "CertificateIssuanceError",
    "CertificateIssuer",
    "IssuanceRequest",
]
