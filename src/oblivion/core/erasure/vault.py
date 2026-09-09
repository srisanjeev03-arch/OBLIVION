"""Recovery Vault for Controlled Recoverable Deletion."""
import json
import logging
import os
from pathlib import Path
from typing import Any, cast

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from oblivion.core.safety.paths import SafePathValidator

logger = logging.getLogger(__name__)

class RecoveryVaultError(Exception):
    pass

class RecoveryVault:
    """Manages the storage and verification of encrypted recovery objects."""

    def __init__(self, vault_root: str, validator: SafePathValidator, key: bytes | None = None):
        self.vault_root = Path(validator.canonicalize(vault_root))
        self.validator = validator
        self._default_key: bytes | None = key

        # Ensure vault exists and is secure
        if not self.vault_root.exists():
            self.vault_root.mkdir(parents=True, exist_ok=True)
            # Basic restrictive permissions for the vault root
            os.chmod(self.vault_root, 0o700)

    def store(self, object_id: str, operation_id: str, target_data: bytes, metadata: dict[str, Any], key: bytes | None = None) -> str:
        """Packages, encrypts, and stores target data.

        Args:
            object_id: Unique identifier for the recovery object.
            operation_id: ID of the operation creating this object.
            target_data: The plaintext payload bytes.
            metadata: Security metadata (original path, SHA-256, size, etc.).
            key: Optional 32-byte AES-256 key. Falls back to the vault's default key.

        Returns:
            The object_id.
        """
        use_key = key if key is not None else self._default_key
        if use_key is None or len(use_key) != 32:
            raise ValueError("Key must be 32 bytes for AES-256")

        aesgcm = AESGCM(use_key)

        # Encrypt the data
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, target_data, None)

        # Enrich metadata
        full_metadata = dict(metadata)
        full_metadata["format_version"] = "1.0"
        full_metadata["object_id"] = object_id
        full_metadata["operation_id"] = operation_id
        full_metadata["nonce_hex"] = nonce.hex()
        full_metadata["original_size"] = len(target_data)

        # Durable atomic write to vault
        payload_path = self.vault_root / f"{object_id}.payload"
        metadata_path = self.vault_root / f"{object_id}.json"
        temp_meta_path = self.vault_root / f"{object_id}.json.tmp_{os.urandom(4).hex()}"
        temp_payload_path = self.vault_root / f"{object_id}.payload.tmp_{os.urandom(4).hex()}"

        try:
            with open(temp_meta_path, "w") as f:
                json.dump(full_metadata, f)
                f.flush()
                os.fsync(f.fileno())

            with open(temp_payload_path, "wb") as f:
                f.write(ciphertext)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename into final locations
            os.replace(temp_meta_path, metadata_path)
            os.replace(temp_payload_path, payload_path)
        except Exception as e:
            if temp_meta_path.exists():
                try:
                    temp_meta_path.unlink()
                except Exception:
                    pass
            if temp_payload_path.exists():
                try:
                    temp_payload_path.unlink()
                except Exception:
                    pass
            logger.error(f"Vault durable write failed: {e}")
            raise RecoveryVaultError("Failed to store recovery object durably")

        return object_id


    def verify_and_decrypt(self, object_id: str, key: bytes) -> bytes:
        """Verifies integrity, decrypts, and returns the payload."""
        if len(key) != 32:
            raise ValueError("Key must be 32 bytes for AES-256")

        aesgcm = AESGCM(key)
        payload_path = self.vault_root / f"{object_id}.payload"
        metadata_path = self.vault_root / f"{object_id}.json"

        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        with open(payload_path, "rb") as f:
            ciphertext = f.read()

        nonce = bytes.fromhex(metadata["nonce_hex"])
        return aesgcm.decrypt(nonce, ciphertext, None)

    def get_metadata(self, object_id: str) -> dict[str, Any]:
        """Reads metadata for a recovery object."""
        metadata_path = self.vault_root / f"{object_id}.json"
        with open(metadata_path, "r") as f:
            data = json.load(f)
            return cast(dict[str, Any], data)

    def exists(self, object_id: str) -> bool:
        """Checks if a recovery object exists."""
        return (self.vault_root / f"{object_id}.payload").exists()

