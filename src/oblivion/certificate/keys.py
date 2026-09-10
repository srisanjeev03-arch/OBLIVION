"""Persistent signing-key lifecycle.

A certificate is only worth something if the identity that signed it outlives
the process that issued it. Before this module the API called
``Ed25519SignerVerifier.generate()`` on first use and cached the result in a
module global, so every restart produced a new keypair and silently invalidated
every certificate already issued. Nothing reported that; verification simply
stopped matching.

This module makes the signing identity *configured* rather than *invented*:

* material comes from the environment, never from source;
* absence or corruption is an error, never a quietly generated replacement;
* the identity is addressed by a stable ``key_id`` derived from the public key,
  so a verifier can tell which key it needs without trusting the certificate;
* rotation is an explicit act that produces a new manager, never an in-place
  mutation of a running one.

**Deployment limitation.** This project has no secret-management platform, so
key material is read from an environment variable or a file on disk. That is
adequate for a controlled test deployment and is *not* adequate for production:
the file is only as protected as its filesystem permissions, and an environment
variable is visible to anything that can read the process environment. The
abstraction here is deliberately narrow so a real key store (DPAPI, a TPM, an
HSM, a cloud KMS) can be added later as another loader without touching callers.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from .signer import Ed25519SignerVerifier

#: Inline key material: 64 hex characters, or a PEM private-key block.
ENV_SIGNING_KEY = "OBLIVION_SIGNING_KEY"
#: Path to a file holding the same material.
ENV_SIGNING_KEY_FILE = "OBLIVION_SIGNING_KEY_FILE"

#: Length of the raw Ed25519 private seed, in bytes.
RAW_PRIVATE_KEY_BYTES = 32


class SigningKeyError(Exception):
    """Raised when a signing identity cannot be established.

    Always fail-closed: callers must treat this as "cannot sign", never as
    "generate something and continue".
    """


@dataclass(frozen=True)
class SigningIdentity:
    """The public half of a signing identity - safe to log, publish and compare."""

    key_id: str
    public_key: bytes

    def public_key_hex(self) -> str:
        return self.public_key.hex()


def derive_key_id(public_key: bytes) -> str:
    """Stable identifier for a public key.

    Derived from the key itself, so it is reproducible anywhere without a
    registry, and changes if and only if the key changes.
    """
    return hashlib.sha256(public_key).hexdigest()[:16]


def _load_private_key(material: str) -> ed25519.Ed25519PrivateKey:
    """Parse hex or PEM private-key material.

    The material is never echoed into the exception message: a failure says what
    was wrong with the shape, not what the value was.
    """
    candidate = material.strip()
    if not candidate:
        raise SigningKeyError("Signing key material is empty")

    try:
        raw = bytes.fromhex(candidate)
    except ValueError:
        raw = b""
    if len(raw) == RAW_PRIVATE_KEY_BYTES:
        return ed25519.Ed25519PrivateKey.from_private_bytes(raw)
    if raw:
        raise SigningKeyError(
            f"Hex signing key must be {RAW_PRIVATE_KEY_BYTES} bytes "
            f"({RAW_PRIVATE_KEY_BYTES * 2} hex characters)"
        )

    try:
        loaded = serialization.load_pem_private_key(
            candidate.encode("utf-8"), password=None
        )
    except Exception as exc:
        raise SigningKeyError(
            "Signing key material is neither valid hex nor a readable PEM "
            f"private key ({type(exc).__name__})"
        ) from None
    if not isinstance(loaded, ed25519.Ed25519PrivateKey):
        raise SigningKeyError("Signing key must be an Ed25519 private key")
    return loaded


class SigningKeyManager:
    """Holds one configured signing identity for the lifetime of a process."""

    def __init__(self, private_key: ed25519.Ed25519PrivateKey):
        self._private_key = private_key
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self._identity = SigningIdentity(
            key_id=derive_key_id(public_bytes), public_key=public_bytes
        )

    # -- construction ------------------------------------------------------

    @classmethod
    def from_material(cls, material: str) -> SigningKeyManager:
        """Build from hex or PEM material supplied by the caller."""
        return cls(_load_private_key(material))

    @classmethod
    def from_file(cls, path: str | Path) -> SigningKeyManager:
        p = Path(path)
        try:
            material = p.read_text(encoding="utf-8")
        except OSError as exc:
            raise SigningKeyError(
                f"Signing key file could not be read: {type(exc).__name__}"
            ) from None
        return cls.from_material(material)

    @classmethod
    def from_environment(cls, env: dict[str, str] | None = None) -> SigningKeyManager:
        """Load the configured identity, or fail.

        Exactly one source must be configured. Supplying both is rejected rather
        than resolved by precedence, so there is never a question about which key
        a deployment is actually signing with.
        """
        source = env if env is not None else os.environ
        inline = source.get(ENV_SIGNING_KEY)
        file_path = source.get(ENV_SIGNING_KEY_FILE)

        if inline and file_path:
            raise SigningKeyError(
                f"Both {ENV_SIGNING_KEY} and {ENV_SIGNING_KEY_FILE} are set; "
                "configure exactly one so the active key is unambiguous"
            )
        if inline:
            return cls.from_material(inline)
        if file_path:
            return cls.from_file(file_path)
        raise SigningKeyError(
            f"No signing key configured. Set {ENV_SIGNING_KEY} or "
            f"{ENV_SIGNING_KEY_FILE}. A key is never generated implicitly, "
            "because a generated key would invalidate every certificate already "
            "issued by this deployment."
        )

    # -- use ---------------------------------------------------------------

    @property
    def identity(self) -> SigningIdentity:
        return self._identity

    @property
    def key_id(self) -> str:
        return self._identity.key_id

    def public_key_bytes(self) -> bytes:
        return self._identity.public_key

    def signer(self) -> Ed25519SignerVerifier:
        """A signer bound to this identity.

        The returned object can sign, but exposes no accessor for the private
        key, so handing it to a caller does not hand over key material.
        """
        return Ed25519SignerVerifier(self._private_key)

    def rotate_to(self, material: str) -> SigningKeyManager:
        """Explicitly adopt new key material, returning a *new* manager.

        Rotation never mutates a running manager: the old identity stays usable
        for verifying what it already signed, and the caller decides when to
        switch. Certificates signed by the previous key remain verifiable
        against the previous ``key_id``.
        """
        return SigningKeyManager.from_material(material)

    # -- containment -------------------------------------------------------

    def __repr__(self) -> str:
        # Never render key material. Logs, tracebacks and reprs are all places a
        # private key must not appear.
        return f"<SigningKeyManager key_id={self._identity.key_id} private_key=REDACTED>"

    __str__ = __repr__


def generate_private_key_hex() -> str:
    """Generate fresh key material for an operator to store.

    This is a provisioning helper for humans. It is intentionally *not* called
    anywhere at runtime: implicit generation is the defect this module exists to
    remove. Persist the returned value in the deployment's secret store and
    expose it through ``OBLIVION_SIGNING_KEY`` or ``OBLIVION_SIGNING_KEY_FILE``.
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return raw.hex()


__all__ = [
    "ENV_SIGNING_KEY",
    "ENV_SIGNING_KEY_FILE",
    "SigningIdentity",
    "SigningKeyError",
    "SigningKeyManager",
    "derive_key_id",
    "generate_private_key_hex",
]
