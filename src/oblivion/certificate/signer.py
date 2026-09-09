
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


class Ed25519SignerVerifier:
    def __init__(self, private_key: ed25519.Ed25519PrivateKey | None = None):
        self._private_key = private_key

    @classmethod
    def generate(cls) -> "Ed25519SignerVerifier":
        private_key = ed25519.Ed25519PrivateKey.generate()
        return cls(private_key)

    def sign(self, data: bytes) -> bytes:
        if not self._private_key:
            raise ValueError("Private key not available for signing.")
        return self._private_key.sign(data)

    @staticmethod
    def verify(public_key_bytes: bytes, data: bytes, signature: bytes) -> bool:
        try:
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            public_key.verify(signature, data)
            return True
        except (InvalidSignature, TypeError, ValueError):
            return False

    def get_public_key_bytes(self) -> bytes:
        if not self._private_key:
            raise ValueError("Private key not available.")
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
