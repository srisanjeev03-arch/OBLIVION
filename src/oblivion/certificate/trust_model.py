"""TrustStore abstractions and implementations for Certificate Signer verification."""
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from .verification_model import CheckResult


@dataclass
class TrustedKey:
    """Represents a trusted signer public key."""
    key_id: str
    public_key_bytes: bytes
    role: str
    valid_from: datetime
    valid_until: datetime | None = None
    revoked: bool = False
    revocation_reason: str | None = None


class TrustStore(ABC):
    """Abstract interface for checking signer trust."""

    @abstractmethod
    def is_trusted(
        self,
        signer_id: str,
        public_key_bytes: bytes,
        at_time: datetime | None = None
    ) -> CheckResult:
        """
        Evaluates trust for a given signer identity and public key bytes.
        Returns:
            CheckResult.PASS if signer identity and key are trusted and active.
            CheckResult.FAIL if explicitly revoked, mismatched key, or invalid validity window.
            CheckResult.NOT_CHECKED if no trust infrastructure exists for the identity.
            CheckResult.INCONCLUSIVE if trust cannot be determined.
        """


class NullTrustStore(TrustStore):
    """Default trust store when no trusted key infrastructure is configured."""

    def is_trusted(
        self,
        signer_id: str,
        public_key_bytes: bytes,
        at_time: datetime | None = None
    ) -> CheckResult:
        return CheckResult.NOT_CHECKED


class StaticTrustStore(TrustStore):
    """In-memory dictionary-backed trust store."""

    def __init__(self, trusted_keys: list[TrustedKey] | None = None):
        self._keys: dict[str, TrustedKey] = {}
        if trusted_keys:
            for k in trusted_keys:
                self._keys[k.key_id] = k

    def add_key(self, key: TrustedKey) -> None:
        self._keys[key.key_id] = key

    def revoke_key(self, key_id: str, reason: str | None = None) -> None:
        if key_id in self._keys:
            self._keys[key_id].revoked = True
            self._keys[key_id].revocation_reason = reason

    def is_trusted(
        self,
        signer_id: str,
        public_key_bytes: bytes,
        at_time: datetime | None = None
    ) -> CheckResult:
        if not self._keys:
            return CheckResult.NOT_CHECKED

        key = self._keys.get(signer_id)
        if key is None:
            return CheckResult.NOT_CHECKED

        # Key bytes must match exactly
        if not isinstance(public_key_bytes, bytes) or not hmac.compare_digest(
            key.public_key_bytes, public_key_bytes
        ):
            return CheckResult.FAIL

        # Revocation check
        if key.revoked:
            return CheckResult.FAIL

        # Validity window check
        check_time = at_time or datetime.now(UTC)
        # Handle naive datetime vs aware datetime comparison
        if check_time.tzinfo is None and key.valid_from.tzinfo is not None:
            check_time = check_time.replace(tzinfo=UTC)
        elif check_time.tzinfo is not None and key.valid_from.tzinfo is None:
            check_time = check_time.replace(tzinfo=None)

        if check_time < key.valid_from:
            return CheckResult.FAIL

        if key.valid_until:
            valid_until = key.valid_until
            if check_time.tzinfo is None and valid_until.tzinfo is not None:
                check_time = check_time.replace(tzinfo=UTC)
            elif check_time.tzinfo is not None and valid_until.tzinfo is None:
                check_time = check_time.replace(tzinfo=None)

            if check_time > valid_until:
                return CheckResult.FAIL

        return CheckResult.PASS


__all__ = ["NullTrustStore", "StaticTrustStore", "TrustStore", "TrustedKey"]
