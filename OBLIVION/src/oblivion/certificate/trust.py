"""Explicit TrustStore for Oblivion certificate signers.

A TrustStore is an explicit, deterministic mapping of signer identity to
trusted Ed25519 public keys. Unknown signers are NEVER implicitly trusted.

Design rules:
- Trust is opt-in. Absence from the store means NOT_TRUSTED.
- Embedded public keys in certificates do NOT confer trust.
- The store is immutable at verification time; mutations go through
  explicit add/remove operations that are themselves audited.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


class TrustStoreError(Exception):
    """Raised when a TrustStore operation cannot be completed safely."""


@dataclass(frozen=True)
class TrustedSigner:
    """An entry in the TrustStore."""

    signer_id: str
    public_key: bytes
    description: str = ""
    added_at: Optional[str] = None

    def key_id(self) -> str:
        import hashlib
        return hashlib.sha256(self.public_key).hexdigest()[:16]

    def matches(self, candidate: bytes) -> bool:
        if not isinstance(candidate, (bytes, bytearray)):
            return False
        if len(candidate) != len(self.public_key):
            return False
        return candidate == self.public_key


@dataclass
class TrustStore:
    """Explicit, deterministic signer trust registry."""

    signers: Dict[str, TrustedSigner] = field(default_factory=dict)
    _key_index: Dict[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        for sid, s in self.signers.items():
            self._key_index[s.key_id()] = sid

    def add_signer(self, signer: TrustedSigner) -> None:
        if not signer.signer_id:
            raise TrustStoreError("signer_id must be non-empty")
        if len(signer.public_key) != 32:
            raise TrustStoreError("public_key must be 32 raw Ed25519 bytes")
        self.signers[signer.signer_id] = signer
        self._key_index[signer.key_id()] = signer.signer_id

    def remove_signer(self, signer_id: str) -> bool:
        existing = self.signers.pop(signer_id, None)
        if existing is None:
            return False
        self._key_index.pop(existing.key_id(), None)
        return True

    def clear(self) -> None:
        self.signers.clear()
        self._key_index.clear()

    def get(self, signer_id: str) -> Optional[TrustedSigner]:
        return self.signers.get(signer_id)

    def find_by_public_key(self, public_key: bytes) -> Optional[TrustedSigner]:
        if not isinstance(public_key, (bytes, bytearray)):
            return None
        if len(public_key) != 32:
            return None
        for signer in self.signers.values():
            if signer.matches(public_key):
                return signer
        return None

    def is_trusted(self, signer_id: str, public_key: bytes) -> bool:
        signer = self.signers.get(signer_id)
        if signer is None:
            return False
        return signer.matches(public_key)

    def is_known_signer(self, signer_id: str) -> bool:
        return signer_id in self.signers

    def __iter__(self) -> Iterator[TrustedSigner]:
        return iter(self.signers.values())

    def __len__(self) -> int:
        return len(self.signers)

    def __contains__(self, signer_id: object) -> bool:
        return signer_id in self.signers


def parse_public_key_bytes(value: str) -> bytes:
    if not isinstance(value, str):
        raise TrustStoreError("public key must be a string")
    candidate = value.strip()
    if not candidate:
        raise TrustStoreError("public key string is empty")
    try:
        raw = bytes.fromhex(candidate)
        if len(raw) == 32:
            return raw
    except ValueError:
        pass
    try:
        pem = candidate.encode("utf-8")
        pub = serialization.load_pem_public_key(pem)
        if isinstance(pub, ed25519.Ed25519PublicKey):
            return pub.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
    except Exception:
        pass
    raise TrustStoreError("Could not parse Ed25519 public key from input")


__all__ = [
    "TrustStore",
    "TrustStoreError",
    "TrustedSigner",
    "parse_public_key_bytes",
]