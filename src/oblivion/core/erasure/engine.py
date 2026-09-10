import hashlib
import logging
import os
import shutil
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

from oblivion.core.erasure.events import EngineEventEmitter
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.state.machine import OperationStateMachine, State, StateMachineError

logger = logging.getLogger(__name__)

class ErasureMode(Enum):
    COMPLETE_ERASURE = auto()
    SELECTIVE_PERMANENT = auto()
    CONTROLLED_RECOVERABLE = auto()


@dataclass(frozen=True)
class ModeCapability:
    """What a mode actually does, and what it therefore cannot prove.

    Kept next to the code that performs the deletion so the claim and the
    behaviour cannot drift apart. See ``docs/COMPLETE_ERASURE_STATUS.md``.
    """

    performs: str
    limitations: tuple[str, ...]


#: Honest capability statements. COMPLETE_ERASURE deliberately does not claim
#: sanitization: this build performs no overwrite of any kind, so the two
#: permanent modes differ in scope (tree vs single file) and not in the
#: guarantee they can offer.
_LOGICAL_ONLY = (
    "Logical deletion only: the filesystem entry is removed. No overwrite of "
    "file contents, slack space, free space or filesystem metadata is performed.",
    "No device or media sanitization is performed or claimed. Content may remain "
    "recoverable from unallocated space, journals, shadow copies, backups or "
    "SSD over-provisioned areas.",
    "Supported scope: NTFS files and directories on a mounted Windows volume.",
)

#: The mode-specific statement leads, so the first limitation a caller reads
#: names the mode and its actual guarantee.
MODE_CAPABILITY: dict[ErasureMode, ModeCapability] = {
    ErasureMode.SELECTIVE_PERMANENT: ModeCapability(
        performs="Unlinks a single validated file.",
        limitations=(
            "SELECTIVE_PERMANENT removes a single validated file by unlinking it. "
            "No overwrite is performed.",
        )
        + _LOGICAL_ONLY,
    ),
    ErasureMode.COMPLETE_ERASURE: ModeCapability(
        performs="Removes a validated directory tree (shutil.rmtree).",
        limitations=(
            "COMPLETE_ERASURE currently provides the same logical removal as "
            "SELECTIVE_PERMANENT, applied to a whole tree. It is NOT a "
            "sanitization mode and must not be described as one.",
        )
        + _LOGICAL_ONLY,
    ),
    ErasureMode.CONTROLLED_RECOVERABLE: ModeCapability(
        performs=(
            "Stores an authenticated encrypted copy in the vault, verifies it by "
            "read-back, then unlinks the original."
        ),
        limitations=(
            "CONTROLLED_RECOVERABLE retains the content in the recovery vault by "
            "design; it is recoverable by an authorized actor holding the vault key.",
        )
        + _LOGICAL_ONLY,
    ),
}

class ErasureEngine:
    """Performs erasure operations on validated targets."""

    def __init__(self, validator: SafePathValidator, event_emitter: EngineEventEmitter):
        self.validator = validator
        self.event_emitter = event_emitter
        self.state_machine = OperationStateMachine()

    def execute_operation(self, mode: ErasureMode, operation_id: str, target_path: str, target_serial: str, target_file_id: tuple[int, int, int] | None = None) -> dict[str, Any]:
        """
        Executes erasure based on mode.
        """
        if mode == ErasureMode.SELECTIVE_PERMANENT:
            return self.execute_selective_permanent_deletion(operation_id, target_path, target_serial, target_file_id)
        elif mode == ErasureMode.COMPLETE_ERASURE:
            return self.execute_complete_erasure(operation_id, target_path, target_serial, target_file_id)
        elif mode == ErasureMode.CONTROLLED_RECOVERABLE:
            return self.execute_controlled_recoverable_deletion(operation_id, target_path, target_serial, target_file_id)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

    def execute_selective_permanent_deletion(self, operation_id: str, target_path: str, target_serial: str, target_file_id: tuple[int, int, int] | None = None) -> dict[str, Any]:
        """
        Executes selective permanent deletion following safety and state machine requirements.
        """
        return self._run_erasure_pipeline(operation_id, target_path, target_serial, target_file_id, ErasureMode.SELECTIVE_PERMANENT)

    def execute_complete_erasure(self, operation_id: str, target_path: str, target_serial: str, target_file_id: tuple[int, int, int] | None = None) -> dict[str, Any]:
        """
        Executes complete erasure following safety and state machine requirements.
        """
        return self._run_erasure_pipeline(operation_id, target_path, target_serial, target_file_id, ErasureMode.COMPLETE_ERASURE)

    def execute_controlled_recoverable_deletion(self, operation_id: str, target_path: str, target_serial: str, target_file_id: tuple[int, int, int] | None = None) -> dict[str, Any]:
        """
        Executes controlled recoverable deletion.
        The original can NEVER be deleted before the recovery object is verified.
        Requires vault, key, and authorization interface to be injected.
        """
        # SECURITY: vault, key, and authorization are required to prevent bypassing
        if not hasattr(self, '_vault') or self._vault is None:
            return {"status": "FAILED", "blocked": ["Vault not configured"], "warnings": [], "successful": [], "failed": []}
        if not hasattr(self, '_vault_key') or self._vault_key is None:
            return {"status": "FAILED", "blocked": ["Vault key not configured"], "warnings": [], "successful": [], "failed": []}

        results: dict[str, Any] = {
            "status": "FAILED",
            "successful": [],
            "failed": [],
            "blocked": [],
            "warnings": [],
            "limitations": list(MODE_CAPABILITY[ErasureMode.CONTROLLED_RECOVERABLE].limitations),
            "vault_object_id": None,
        }

        try:
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.CREATED.name, "mode": ErasureMode.CONTROLLED_RECOVERABLE.name})

            self.state_machine.transition_to(State.ANALYZING)
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.ANALYZING.name})

            validation = self.validator.validate_target(target_path)
            if not validation["valid"]:
                self.event_emitter.emit("SAFETY_VIOLATION", operation_id, target_path, {"errors": validation["errors"]})
                results["blocked"] = validation["errors"]
                self.state_machine.transition_to(State.FAILED)
                return results

            # Capture original SHA-256 BEFORE deletion
            target = Path(target_path)
            if not target.is_file():
                results["blocked"].append("Controlled recoverable deletion only supports files")
                self.state_machine.transition_to(State.FAILED)
                return results

            original_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            self.event_emitter.emit("HASH_CAPTURED", operation_id, target_path, {"sha256": original_hash})

            self.state_machine.transition_to(State.READY)
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.READY.name})

            # Create recovery object
            object_id = f"{operation_id}-{original_hash[:8]}"
            metadata = {
                "original_path": str(target_path),
                "original_sha256": original_hash,
                "original_size": target.stat().st_size,
                "created_at": str(Path(target_path).stat().st_mtime),
            }

            self.event_emitter.emit("RECOVERY_OBJECT_CREATION", operation_id, target_path, {"object_id": object_id})
            self.event_emitter.emit("ENCRYPTION_COMPLETED", operation_id, target_path, {"object_id": object_id})

            try:
                payload = target.read_bytes()
                self._vault.store(object_id, operation_id, payload, metadata, self._vault_key)
            except Exception as e:
                logger.error(f"Vault store failed: {type(e).__name__}")
                self.event_emitter.emit("VAULT_WRITE_FAILED", operation_id, target_path, {"object_id": object_id})
                results["blocked"].append("Vault write failed - original remains intact")
                self.state_machine.transition_to(State.FAILED)
                return results

            self.event_emitter.emit("VAULT_PERSISTED", operation_id, target_path, {"object_id": object_id})

            # Verify recovery object (read-back, decrypt, hash-match)
            try:
                recovered_payload = self._vault.verify_and_decrypt(object_id, self._vault_key)
            except Exception as e:
                logger.error(f"Vault verification failed: {type(e).__name__}")
                self.event_emitter.emit("VAULT_VERIFICATION_FAILED", operation_id, target_path, {"object_id": object_id})
                results["blocked"].append("Vault verification failed - original remains intact")
                self.state_machine.transition_to(State.FAILED)
                return results

            self.event_emitter.emit("RECOVERY_OBJECT_VERIFICATION", operation_id, target_path, {"object_id": object_id})

            recovered_hash = hashlib.sha256(recovered_payload).hexdigest()
            if recovered_hash != original_hash:
                self.event_emitter.emit("HASH_MISMATCH", operation_id, target_path, {"object_id": object_id})
                results["blocked"].append("Hash mismatch - original remains intact")
                self.state_machine.transition_to(State.FAILED)
                return results

            self.event_emitter.emit("HASH_VERIFIED", operation_id, target_path, {"object_id": object_id})

            # Final TOCTOU revalidation AFTER vault verification, IMMEDIATELY before deletion
            self.state_machine.transition_to(State.ERASING)
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.ERASING.name})

            if not self.validator.revalidate_handle(target_path, target_serial, target_file_id):
                self.event_emitter.emit("TOCTOU_FAILURE", operation_id, target_path, {"error": "Final TOCTOU revalidation failed"})
                self.state_machine.transition_to(State.FAILED)
                results["blocked"].append("Final TOCTOU revalidation failed - original remains intact")
                return results

            # All preconditions met - delete original
            try:
                target.unlink()
            except Exception as e:
                logger.error(f"Original deletion failed: {type(e).__name__}")
                self.event_emitter.emit("ERASURE_ERROR", operation_id, target_path, {"error": "Original deletion failed"})
                results["failed"].append(target_path)
                self.state_machine.transition_to(State.FAILED)
                return results

            self.event_emitter.emit("ORIGINAL_DELETED", operation_id, target_path, {"object_id": object_id})

            # Verify deletion
            if not target.exists():
                self.state_machine.transition_to(State.VERIFYING)
                self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.VERIFYING.name})
                self.state_machine.transition_to(State.COMPLETED)
                self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.COMPLETED.name})
                self.event_emitter.emit("RECOVERABLE_DELETION_SUCCESS", operation_id, target_path, {"object_id": object_id})
                results["status"] = "COMPLETED"
                results["successful"].append(target_path)
                results["vault_object_id"] = object_id
            else:
                self.state_machine.transition_to(State.PARTIAL)
                self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.PARTIAL.name})
                results["status"] = "PARTIAL"
                results["vault_object_id"] = object_id

        except StateMachineError as e:
            logger.error(f"State machine error: {e}")
            results["blocked"].append(str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}")
            results["failed"].append("Unexpected error during recoverable deletion")

        return results

    def restore_recovery_object(self, object_id: str, destination_path: str, key: bytes, authorized: bool = False, allow_overwrite: bool = False) -> dict[str, Any]:
        """Minimum restore operation. Requires explicit authorization. Defaults to non-overwriting."""
        if not authorized:
            return {"status": "BLOCKED", "error": "Restore not authorized"}

        # Check existing destination
        if os.path.exists(destination_path) and not allow_overwrite:
            return {
                "status": "BLOCKED",
                "error": f"Destination file '{destination_path}' already exists (overwrite rejected by default)",
            }

        # Validate destination
        # A new destination has no file identity yet.  It is still constrained
        # to the allowed root, reparse checks, and system-volume protection.
        dest_validation = self.validator.validate_target(destination_path, require_existing_identity=False)
        if not dest_validation["valid"]:
            return {"status": "BLOCKED", "error": f"Destination validation failed: {dest_validation['errors']}"}

        try:
            payload = self._vault.verify_and_decrypt(object_id, key)
        except Exception:
            return {"status": "FAILED", "error": "Decryption or authentication failed"}

        metadata = self._vault.get_metadata(object_id)
        original_hash = metadata.get("original_sha256")
        recovered_hash = hashlib.sha256(payload).hexdigest()

        if original_hash != recovered_hash:
            return {"status": "FAILED", "error": "Recovered hash does not match original"}

        # Write to destination atomically and durably
        temp_dest = f"{destination_path}.tmp_{os.urandom(4).hex()}"
        try:
            with open(temp_dest, "wb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_dest, destination_path)
        except Exception as e:
            if os.path.exists(temp_dest):
                try:
                    os.unlink(temp_dest)
                except Exception:
                    pass
            return {"status": "FAILED", "error": f"Write failed: {e}"}

        return {
            "status": "COMPLETED",
            "destination": destination_path,
            "sha256": recovered_hash,
            "integrity_verified": True,
        }


    def set_vault(self, vault: RecoveryVault, key: bytes) -> None:
        """Configures the recovery vault and key for the engine."""
        self._vault = vault
        self._vault_key = key

    def _run_erasure_pipeline(self, operation_id: str, target_path: str, target_serial: str, target_file_id: tuple[int, int, int] | None = None, mode: ErasureMode = ErasureMode.SELECTIVE_PERMANENT) -> dict[str, Any]:
        results: dict[str, Any] = {
            "status": "FAILED",
            "successful": [],
            "failed": [],
            "blocked": [],
            "warnings": [],
            "limitations": list(MODE_CAPABILITY[mode].limitations),
        }

        try:
            # 1. CREATED
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.CREATED.name, "mode": mode.name})

            # 2. ANALYZING
            self.state_machine.transition_to(State.ANALYZING)
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.ANALYZING.name})

            validation = self.validator.validate_target(target_path)
            if not validation["valid"]:
                self.event_emitter.emit("SAFETY_VIOLATION", operation_id, target_path, {"errors": validation["errors"]})
                results["blocked"] = validation["errors"]
                self.state_machine.transition_to(State.FAILED)
                return results

            # 3. READY
            self.state_machine.transition_to(State.READY)
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.READY.name})

            # 4. ERASING
            # Final TOCTOU revalidation
            if not self.validator.revalidate_handle(target_path, target_serial, target_file_id):
                self.event_emitter.emit("SAFETY_VIOLATION", operation_id, target_path, {"error": "TOCTOU revalidation failed"})
                self.state_machine.transition_to(State.FAILED)
                results["blocked"].append("TOCTOU revalidation failed")
                return results

            # Structurally enforced safe path
            return self._perform_erasure(operation_id, target_path, results, mode)

        except StateMachineError as e:
            logger.error(f"State machine error: {e}")
            results["blocked"].append(str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            results["failed"].append(str(e))

        return results

    def _perform_erasure(self, operation_id: str, target_path: str, results: dict[str, Any], mode: ErasureMode) -> dict[str, Any]:
        """Performs deletion after final safety verification."""
        self.state_machine.transition_to(State.ERASING)
        self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.ERASING.name})

        # Both permanent modes perform the same logical removal. Neither
        # overwrites content: no sanitization pass exists in this build, and the
        # reported limitations say so. Adding an overwrite here would change what
        # the product may claim, so it is a deliberate implementation decision
        # rather than a line of code - see docs/COMPLETE_ERASURE_STATUS.md.
        logger.info("Performing %s (logical removal) on %s", mode.name, target_path)

        target = Path(target_path)
        try:
            if target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target_path)
            else:
                raise ValueError(f"Unsupported target type: {target_path}")
            results["successful"].append(target_path)
        except Exception as e:
            logger.error(f"Deletion failed: {e}")
            self.event_emitter.emit("ERASURE_ERROR", operation_id, target_path, {"error": str(e)})
            results["failed"].append(target_path)
            self.state_machine.transition_to(State.FAILED)
            return results

        # 5. VERIFYING
        self.state_machine.transition_to(State.VERIFYING)
        self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.VERIFYING.name})

        if not os.path.exists(target_path):
            # 6. COMPLETED
            self.state_machine.transition_to(State.COMPLETED)
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.COMPLETED.name})
            results["status"] = "COMPLETED"
        else:
            self.state_machine.transition_to(State.PARTIAL)
            self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.PARTIAL.name})
            results["status"] = "PARTIAL"
            results["warnings"].append("Target still exists after erasure attempt")

        return results
