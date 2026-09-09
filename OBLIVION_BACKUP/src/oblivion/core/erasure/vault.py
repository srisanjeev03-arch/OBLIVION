"""Recovery Vault for Controlled Recoverable Deletion."""
import os
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, cast
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from oblivion.core.safety.paths import SafePathValidator

logger = logging.getLogger(__name__)

class RecoveryVaultError(Exception):
    pass

class RecoveryVault:
    """Manages the storage and verification of encrypted recovery objects."""

    def __init__(self, vault_root: str, validator: SafePathValidator, key: Optional[bytes] = None):
        self.vault_root = Path(validator.canonicalize(vault_root))
        self.validator = validator
        self._default_key: Optional[bytes] = key

        # Ensure vault exists and is secure
        if not self.vault_root.exists():
            self.vault_root.mkdir(parents=True, exist_ok=True)
            # Basic restrictive permissions for the vault root
            os.chmod(self.vault_root, 0o700)

    def store(self, object_id: str, operation_id: str, target_data: bytes, metadata: Dict[str, Any], key: Optional[bytes] = None) -> str:
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

        # Write to vault
        payload_path = self.vault_root / f"{object_id}.payload"
        metadata_path = self.vault_root / f"{object_id}.json"

        try:
            with open(metadata_path, "w") as f:
                json.dump(full_metadata, f)
            with open(payload_path, "wb") as f:
                f.write(ciphertext)
        except Exception as e:
            logger.error(f"Vault write failed: {e}")
            raise RecoveryVaultError("Failed to store recovery object")

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

    def get_metadata(self, object_id: str) -> Dict[str, Any]:
        """Reads metadata for a recovery object."""
        metadata_path = self.vault_root / f"{object_id}.json"
        with open(metadata_path, "r") as f:
            data = json.load(f)
            return cast(Dict[str, Any], data)

    def exists(self, object_id: str) -> bool:
        """Checks if a recovery object exists."""
        return (self.vault_root / f"{object_id}.payload").exists()

