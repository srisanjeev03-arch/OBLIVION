import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from oblivion.core.erasure.engine import ErasureEngine, ErasureMode
from oblivion.core.erasure.events import EngineEventEmitter
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.safety.paths import SafePathValidator


@pytest.fixture
def engine(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_root = Path(tmpdir) / "vault"
        allowed_root = Path(tmpdir) / "data"
        allowed_root.mkdir()

        key = os.urandom(32)
        validator = SafePathValidator(allowed_roots=[str(allowed_root)])
        monkeypatch.setattr(validator, "is_system_volume", lambda path: False)

        vault = RecoveryVault(str(vault_root), validator, key)
        emitter = MagicMock(spec=EngineEventEmitter)

        eng = ErasureEngine(validator, emitter)
        eng.set_vault(vault, key)

        yield eng, allowed_root, emitter, key, vault


def _get_file_serial_id(eng, path):
    return eng.validator.get_volume_serial(str(path)), eng.validator._get_file_id(str(path))


def test_controlled_recoverable_deletion_success(engine):
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    file_path.write_text("secure content")
    serial, file_id = _get_file_serial_id(eng, file_path)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_success",
        str(file_path),
        serial,
        target_file_id=file_id
    )

    assert result["status"] == "COMPLETED"
    assert not file_path.exists()
    assert result["vault_object_id"] is not None
    assert vault.exists(result["vault_object_id"])


def test_controlled_recoverable_vault_write_failure_preserves_original(engine, monkeypatch):
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    file_path.write_text("secure")
    serial, file_id = _get_file_serial_id(eng, file_path)

    def failing_store(*args, **kwargs):
        raise RuntimeError("simulated disk failure")

    monkeypatch.setattr(vault, "store", failing_store)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_vault_fail",
        str(file_path),
        serial,
        target_file_id=file_id
    )

    assert result["status"] == "FAILED"
    assert file_path.exists()  # Original remains intact
    assert file_path.read_text() == "secure"


def test_controlled_recoverable_vault_verify_failure_preserves_original(engine, monkeypatch):
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    file_path.write_text("secure")
    serial, file_id = _get_file_serial_id(eng, file_path)

    def failing_verify(*args, **kwargs):
        raise RuntimeError("simulated auth failure")

    monkeypatch.setattr(vault, "verify_and_decrypt", failing_verify)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_verify_fail",
        str(file_path),
        serial,
        target_file_id=file_id
    )

    assert result["status"] == "FAILED"
    assert file_path.exists()  # Original remains intact


def test_controlled_recoverable_toctou_failure_preserves_original(engine, monkeypatch):
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    file_path.write_text("secure")
    serial, file_id = _get_file_serial_id(eng, file_path)

    # Force revalidate to fail
    monkeypatch.setattr(eng.validator, "revalidate_handle", lambda *args, **kwargs: False)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_toctou_fail",
        str(file_path),
        serial,
        target_file_id=file_id
    )

    assert result["status"] == "FAILED"
    assert file_path.exists()  # Original remains intact


def test_controlled_recoverable_safety_violation_preserves_original(engine, monkeypatch):
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    file_path.write_text("secure")
    serial, file_id = _get_file_serial_id(eng, file_path)

    # Force safety validation to fail
    monkeypatch.setattr(eng.validator, "validate_target", lambda p: {"valid": False, "errors": ["blocked"]})

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_safety_fail",
        str(file_path),
        serial,
        target_file_id=file_id
    )

    assert result["status"] == "FAILED"
    assert file_path.exists()


def test_controlled_recoverable_unauthorized_restore_blocked(engine):
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    file_path.write_text("secure")
    serial, file_id = _get_file_serial_id(eng, file_path)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_restore_test",
        str(file_path),
        serial,
        target_file_id=file_id
    )
    obj_id = result["vault_object_id"]

    dest = allowed_root / "restored.txt"
    restore_result = eng.restore_recovery_object(
        obj_id, str(dest), key, authorized=False
    )
    assert restore_result["status"] == "BLOCKED"


def test_controlled_recoverable_authorized_restore(engine):
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    original_content = "secure content"
    file_path.write_text(original_content)
    serial, file_id = _get_file_serial_id(eng, file_path)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_restore_ok",
        str(file_path),
        serial,
        target_file_id=file_id
    )
    obj_id = result["vault_object_id"]

    dest = allowed_root / "restored.txt"
    restore_result = eng.restore_recovery_object(
        obj_id, str(dest), key, authorized=True
    )
    assert restore_result["status"] == "COMPLETED"
    assert dest.read_text() == original_content


def test_controlled_recoverable_crypto_round_trip(engine):
    """Verify encryption/decryption round trip and that plaintext is not stored."""
    eng, allowed_root, emitter, key, vault = engine
    plaintext = b"this is sensitive content that must not be stored in cleartext"
    file_path = allowed_root / "secret.txt"
    file_path.write_bytes(plaintext)
    serial, file_id = _get_file_serial_id(eng, file_path)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_crypto_rt",
        str(file_path),
        serial,
        target_file_id=file_id
    )
    obj_id = result["vault_object_id"]

    # Verify the raw payload file does NOT contain plaintext
    raw_payload = (Path(vault.vault_root) / f"{obj_id}.payload").read_bytes()
    assert plaintext not in raw_payload
    assert raw_payload != plaintext

    # Verify decryption round trip
    decrypted = vault.verify_and_decrypt(obj_id, key)
    assert decrypted == plaintext


def test_controlled_recoverable_tampered_ciphertext_detected(engine):
    """Verify that ciphertext tampering causes authentication failure."""
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    file_path.write_text("secure")
    serial, file_id = _get_file_serial_id(eng, file_path)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_tamper",
        str(file_path),
        serial,
        target_file_id=file_id
    )
    obj_id = result["vault_object_id"]

    # Tamper with ciphertext
    payload_path = Path(vault.vault_root) / f"{obj_id}.payload"
    tampered = bytearray(payload_path.read_bytes())
    if len(tampered) > 0:
        tampered[0] ^= 0xFF
    payload_path.write_bytes(bytes(tampered))

    # Verification should fail
    with pytest.raises(Exception):
        vault.verify_and_decrypt(obj_id, key)


def test_controlled_recoverable_wrong_key_fails(engine):
    """Verify that wrong key cannot decrypt."""
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    file_path.write_text("secure")
    serial, file_id = _get_file_serial_id(eng, file_path)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_wrong_key",
        str(file_path),
        serial,
        target_file_id=file_id
    )
    obj_id = result["vault_object_id"]

    wrong_key = os.urandom(32)
    with pytest.raises(Exception):
        vault.verify_and_decrypt(obj_id, wrong_key)


def test_controlled_recoverable_recovered_hash_matches_original(engine):
    """Verify hash integrity between original and recovered payload."""
    eng, allowed_root, emitter, key, vault = engine
    file_path = allowed_root / "test.txt"
    original_content = b"integrity test"
    file_path.write_bytes(original_content)
    serial, file_id = _get_file_serial_id(eng, file_path)

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_hash_check",
        str(file_path),
        serial,
        target_file_id=file_id
    )
    obj_id = result["vault_object_id"]

    decrypted = vault.verify_and_decrypt(obj_id, key)
    recovered_hash = hashlib.sha256(decrypted).hexdigest()
    expected_hash = hashlib.sha256(original_content).hexdigest()
    assert recovered_hash == expected_hash


def test_controlled_recoverable_outside_allowed_scope_blocked(engine):
    eng, allowed_root, emitter, key, vault = engine
    blocked_path = allowed_root.parent / "outside.txt"
    blocked_path.write_text("evil")

    result = eng.execute_operation(
        ErasureMode.CONTROLLED_RECOVERABLE,
        "op_outside",
        str(blocked_path),
        "SERIAL"
    )
    assert result["status"] == "FAILED"
    assert blocked_path.exists()
