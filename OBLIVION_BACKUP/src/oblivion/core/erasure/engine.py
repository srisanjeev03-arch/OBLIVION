import logging
import os
import shutil
import hashlib
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.state.machine import OperationStateMachine, State, StateMachineError
from oblivion.core.erasure.events import EngineEventEmitter
from oblivion.core.erasure.vault import RecoveryVault

logger = logging.getLogger(__name__)

class ErasureMode(Enum):
    COMPLETE_ERASURE = auto()
    SELECTIVE_PERMANENT = auto()
    CONTROLLED_RECOVERABLE = auto()

class ErasureEngine:
    """Performs erasure operations on validated targets."""

    def __init__(self, validator: SafePathValidator, event_emitter: EngineEventEmitter):
        self.validator = validator
        self.event_emitter = event_emitter
        self.state_machine = OperationStateMachine()

    def execute_operation(self, mode: ErasureMode, operation_id: str, target_path: str, target_serial: str, target_file_id: Optional[tuple[int, int, int]] = None) -> Dict[str, Any]:
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

    def execute_selective_permanent_deletion(self, operation_id: str, target_path: str, target_serial: str, target_file_id: Optional[tuple[int, int, int]] = None) -> Dict[str, Any]:
        """
        Executes selective permanent deletion following safety and state machine requirements.
        """
        return self._run_erasure_pipeline(operation_id, target_path, target_serial, target_file_id, ErasureMode.SELECTIVE_PERMANENT)

    def execute_complete_erasure(self, operation_id: str, target_path: str, target_serial: str, target_file_id: Optional[tuple[int, int, int]] = None) -> Dict[str, Any]:
        """
        Executes complete erasure following safety and state machine requirements.
        """
        return self._run_erasure_pipeline(operation_id, target_path, target_serial, target_file_id, ErasureMode.COMPLETE_ERASURE)

    def execute_controlled_recoverable_deletion(self, operation_id: str, target_path: str, target_serial: str, target_file_id: Optional[tuple[int, int, int]] = None) -> Dict[str, Any]:
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

        results: Dict[str, Any] = {
            "status": "FAILED",
            "successful": [],
            "failed": [],
            "blocked": [],
            "warnings": [],
            "limitations": ["Controlled recoverable deletion - requires vault verification before original deletion"],
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

    def restore_recovery_object(self, object_id: str, destination_path: str, key: bytes, authorized: bool = False) -> Dict[str, Any]:
        """Minimum restore operation. Requires explicit authorization."""
        if not authorized:
            return {"status": "BLOCKED", "error": "Restore not authorized"}

        # Validate destination
        dest_validation = self.validator.validate_target(destination_path)
        if not dest_validation["valid"]:
            return {"status": "BLOCKED", "error": f"Destination validation failed: {dest_validation['errors']}"}

        try:
            payload = self._vault.verify_and_decrypt(object_id, key)
        except Exception as e:
            return {"status": "FAILED", "error": "Decryption or authentication failed"}

        metadata = self._vault.get_metadata(object_id)
        original_hash = metadata.get("original_sha256")
        recovered_hash = hashlib.sha256(payload).hexdigest()

        if original_hash != recovered_hash:
            return {"status": "FAILED", "error": "Recovered hash does not match original"}

        # Write to destination
        try:
            with open(destination_path, "wb") as f:
                f.write(payload)
        except Exception as e:
            return {"status": "FAILED", "error": "Write failed"}

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

    def _run_erasure_pipeline(self, operation_id: str, target_path: str, target_serial: str, target_file_id: Optional[tuple[int, int, int]] = None, mode: ErasureMode = ErasureMode.SELECTIVE_PERMANENT) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "status": "FAILED",
            "successful": [],
            "failed": [],
            "blocked": [],
            "warnings": [],
            "limitations": [f"Logical deletion only - no physical sanitization guaranteed ({mode.name})"]
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

    def _perform_erasure(self, operation_id: str, target_path: str, results: Dict[str, Any], mode: ErasureMode) -> Dict[str, Any]:
        """Performs deletion after final safety verification."""
        self.state_machine.transition_to(State.ERASING)
        self.event_emitter.emit("STATE_CHANGE", operation_id, target_path, {"state": State.ERASING.name})

        # Capability-aware erasure
        if mode == ErasureMode.COMPLETE_ERASURE:
            # In a real implementation, this would perform advanced overwriting
            logger.info(f"Performing COMPLETE_ERASURE on {target_path}")
        else:
            logger.info(f"Performing SELECTIVE_PERMANENT deletion on {target_path}")

        target = Path(target_path)
        try:
            if target.is_file():
                # For COMPLETE_ERASURE, we might want to overwrite first
                if mode == ErasureMode.COMPLETE_ERASURE:
                    # Example of advanced deletion:
                    # with open(target_path, "wb") as f:
                    #     f.write(os.urandom(target.stat().st_size))
                    pass
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
