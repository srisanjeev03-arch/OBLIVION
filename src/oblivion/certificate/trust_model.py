"""Who the *verifier* is willing to believe.

The TrustStore answers a question the certificate cannot answer about itself:
is this signer trusted here? A certificate carries a public key, and that key
may well verify the signature - but a forger's key verifies a forger's signature
just as cleanly. Trust has to come from configuration on the verifying side, and
that is all this module is.

Three properties are kept deliberately separate, and the verifier reports them
separately:

* the signature verifies mathematically    -> SIGNATURE_VALIDITY
* the embedded key matches the trusted one -> PUBLIC_KEY_CONSISTENCY
* the signer is trusted here               -> SIGNER_TRUST

There is no "trust everything" mode. An unconfigured store returns
``NOT_CHECKED``, which aggregates to ``INCONCLUSIVE`` - honest about the fact
that no trust decision was possible.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .verification_model import CheckResult

#: ``signer_id:<64 hex public key>`` pairs, comma-separated.
ENV_TRUSTED_SIGNERS = "OBLIVION_TRUSTED_SIGNERS"


class TrustStoreError(Exception):
    """Raised when trust configuration cannot be interpreted."""


@dataclass(frozen=True)
class TrustedKey:
    """One explicitly trusted signer key."""

    signer_id: str
    public_key_bytes: bytes
    role: str = "issuer"
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    revoked: bool = False
    revocation_reason: str | None = None

    @property
    def key_id(self) -> str:
        return hashlib.sha256(self.public_key_bytes).hexdigest()[:16]

    def matches(self, candidate: bytes) -> bool:
        """Constant-time comparison against a candidate key."""
        if not isinstance(candidate, (bytes, bytearray)):
            return False
        if len(candidate) != len(self.public_key_bytes):
            return False
        return hmac.compare_digest(bytes(candidate), self.public_key_bytes)


class TrustStore(ABC):
    """Interface every trust source implements."""

    @abstractmethod
    def lookup(self, signer_id: str) -> TrustedKey | None:
        """The trusted key for ``signer_id``, or None when the signer is unknown.

        This is what makes verification independent: the key returned here comes
        from the verifier's configuration, not from the certificate.
        """

    @abstractmethod
    def is_trusted(
        self,
        signer_id: str,
        public_key_bytes: bytes,
        at_time: datetime | None = None,
    ) -> CheckResult:
        """Trust verdict for a signer presenting ``public_key_bytes``."""


class NullTrustStore(TrustStore):
    """The default: no trust anchors configured, so no trust can be established.

    Returns ``NOT_CHECKED`` rather than ``FAIL``. Nothing is known to be
    untrustworthy - nothing is known at all, and the aggregate says so by
    landing on INCONCLUSIVE.
    """

    def lookup(self, signer_id: str) -> TrustedKey | None:
        return None

    def is_trusted(
        self,
        signer_id: str,
        public_key_bytes: bytes,
        at_time: datetime | None = None,
    ) -> CheckResult:
        return CheckResult.NOT_CHECKED


@dataclass
class StaticTrustStore(TrustStore):
    """An explicitly configured set of trusted signers."""

    keys: dict[str, TrustedKey] = field(default_factory=dict)
    #: Signers explicitly declared untrusted, e.g. after compromise.
    denied: set[str] = field(default_factory=set)

    @classmethod
    def from_keys(cls, trusted: list[TrustedKey]) -> StaticTrustStore:
        return cls(keys={k.signer_id: k for k in trusted})

    def add(self, key: TrustedKey) -> None:
        if not key.signer_id:
            raise TrustStoreError("signer_id must be non-empty")
        if len(key.public_key_bytes) != 32:
            raise TrustStoreError("public_key_bytes must be 32 raw Ed25519 bytes")
        self.keys[key.signer_id] = key

    def deny(self, signer_id: str) -> None:
        """Mark a signer explicitly untrusted, distinct from merely unknown."""
        self.denied.add(signer_id)

    def revoke(self, signer_id: str, reason: str | None = None) -> None:
        existing = self.keys.get(signer_id)
        if existing is not None:
            self.keys[signer_id] = TrustedKey(
                signer_id=existing.signer_id,
                public_key_bytes=existing.public_key_bytes,
                role=existing.role,
                valid_from=existing.valid_from,
                valid_until=existing.valid_until,
                revoked=True,
                revocation_reason=reason,
            )

    def lookup(self, signer_id: str) -> TrustedKey | None:
        return self.keys.get(signer_id)

    def is_trusted(
        self,
        signer_id: str,
        public_key_bytes: bytes,
        at_time: datetime | None = None,
    ) -> CheckResult:
        if signer_id in self.denied:
            return CheckResult.FAIL

        key = self.keys.get(signer_id)
        if key is None:
            # Unknown is not the same as untrusted.
            return CheckResult.NOT_CHECKED

        if not key.matches(public_key_bytes):
            # A known signer presenting a different key is a real failure, not
            # an unknown: someone is claiming an identity they cannot back.
            return CheckResult.FAIL

        if key.revoked:
            return CheckResult.FAIL

        moment = at_time or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)

        if key.valid_from is not None:
            start = key.valid_from
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            if moment < start:
                return CheckResult.FAIL

        if key.valid_until is not None:
            end = key.valid_until
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
            if moment > end:
                return CheckResult.FAIL

        return CheckResult.PASS


def load_trust_store_from_env(env: dict[str, str] | None = None) -> TrustStore:
    """Build the configured trust store, or a NullTrustStore when unconfigured.

    Format: ``signer_id:<64 hex public key>``, comma-separated. Only public keys
    appear here; nothing in this file reads private material.
    """
    source = env if env is not None else os.environ
    raw = (source.get(ENV_TRUSTED_SIGNERS) or "").strip()
    if not raw:
        return NullTrustStore()

    store = StaticTrustStore()
    for entry in raw.split(","):
        item = entry.strip()
        if not item:
            continue
        signer_id, separator, key_hex = item.partition(":")
        if not separator or not signer_id.strip() or not key_hex.strip():
            raise TrustStoreError(
                f"{ENV_TRUSTED_SIGNERS} entries must be 'signer_id:<hex public key>'"
            )
        try:
            key_bytes = bytes.fromhex(key_hex.strip())
        except ValueError:
            raise TrustStoreError(
                f"Trusted key for signer {signer_id.strip()!r} is not valid hex"
            ) from None
        store.add(TrustedKey(signer_id=signer_id.strip(), public_key_bytes=key_bytes))
    return store


__all__ = [
    "ENV_TRUSTED_SIGNERS",
    "NullTrustStore",
    "StaticTrustStore",
    "TrustStore",
    "TrustStoreError",
    "TrustedKey",
    "load_trust_store_from_env",
]
