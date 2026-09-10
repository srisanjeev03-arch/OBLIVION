"""Signing-key lifecycle.

The property under test is that a deployment's signing identity is stable and
configured. Previously the API generated a keypair on first use, so the identity
changed on every restart and certificates issued before a restart could no
longer be verified after it. Nothing in the system reported that; verification
simply stopped matching.

All key material below is generated inside the tests. No real deployment key
appears in this file.
"""

import pytest
from fastapi import HTTPException

from oblivion.api import dependencies
from oblivion.certificate.keys import (
    ENV_SIGNING_KEY,
    ENV_SIGNING_KEY_FILE,
    SigningKeyError,
    SigningKeyManager,
    derive_key_id,
    generate_private_key_hex,
)
from oblivion.certificate.signer import Ed25519SignerVerifier


@pytest.fixture
def key_material():
    return generate_private_key_hex()


@pytest.fixture(autouse=True)
def _clear_cached_manager():
    """Each test starts from an unconfigured process."""
    dependencies.reset_signing_key_manager()
    yield
    dependencies.reset_signing_key_manager()


# -- identity is stable across process instances ---------------------------

def test_same_identity_across_process_instances(key_material):
    """Two independently constructed managers agree on the identity."""
    first = SigningKeyManager.from_material(key_material)
    second = SigningKeyManager.from_material(key_material)

    assert first.key_id == second.key_id
    assert first.public_key_bytes() == second.public_key_bytes()


def test_signature_verifies_after_simulated_restart(key_material):
    """A signature made before a restart still verifies after it."""
    before_restart = SigningKeyManager.from_material(key_material)
    payload = b"evidence-digest-stand-in"
    signature = before_restart.signer().sign(payload)

    # A new process loads the same configured material.
    after_restart = SigningKeyManager.from_material(key_material)

    assert Ed25519SignerVerifier.verify(
        after_restart.public_key_bytes(), payload, signature
    ) is True


def test_distinct_material_yields_distinct_identity():
    a = SigningKeyManager.from_material(generate_private_key_hex())
    b = SigningKeyManager.from_material(generate_private_key_hex())
    assert a.key_id != b.key_id


def test_key_id_is_derived_from_the_public_key(key_material):
    manager = SigningKeyManager.from_material(key_material)
    assert manager.key_id == derive_key_id(manager.public_key_bytes())
    assert len(manager.key_id) == 16


# -- public-key consistency ------------------------------------------------

def test_public_key_matches_the_signing_key(key_material):
    """The advertised public key is the one that actually verifies signatures."""
    manager = SigningKeyManager.from_material(key_material)
    payload = b"payload"
    signature = manager.signer().sign(payload)

    assert Ed25519SignerVerifier.verify(manager.public_key_bytes(), payload, signature)
    assert len(manager.public_key_bytes()) == 32
    assert manager.identity.public_key_hex() == manager.public_key_bytes().hex()


def test_a_different_key_does_not_verify(key_material):
    manager = SigningKeyManager.from_material(key_material)
    other = SigningKeyManager.from_material(generate_private_key_hex())
    signature = manager.signer().sign(b"payload")

    assert Ed25519SignerVerifier.verify(
        other.public_key_bytes(), b"payload", signature
    ) is False


# -- fail-closed loading ---------------------------------------------------

def test_missing_key_is_an_error_not_a_generated_one():
    with pytest.raises(SigningKeyError) as exc:
        SigningKeyManager.from_environment(env={})
    assert "No signing key configured" in str(exc.value)


def test_malformed_hex_key_is_rejected():
    with pytest.raises(SigningKeyError):
        SigningKeyManager.from_material("not-a-key")


def test_wrong_length_hex_key_is_rejected():
    with pytest.raises(SigningKeyError) as exc:
        SigningKeyManager.from_material("aa" * 16)  # 16 bytes, not 32
    assert "32 bytes" in str(exc.value)


def test_empty_key_is_rejected():
    with pytest.raises(SigningKeyError):
        SigningKeyManager.from_material("   ")


def test_ambiguous_configuration_is_rejected(key_material):
    """Two configured sources must not silently resolve by precedence."""
    with pytest.raises(SigningKeyError) as exc:
        SigningKeyManager.from_environment(
            env={ENV_SIGNING_KEY: key_material, ENV_SIGNING_KEY_FILE: "some/path"}
        )
    assert "exactly one" in str(exc.value)


def test_unreadable_key_file_is_an_error(tmp_path):
    with pytest.raises(SigningKeyError) as exc:
        SigningKeyManager.from_file(tmp_path / "absent.key")
    assert "could not be read" in str(exc.value)


# -- loading from configured sources ---------------------------------------

def test_loads_from_environment_variable(key_material):
    manager = SigningKeyManager.from_environment(env={ENV_SIGNING_KEY: key_material})
    assert manager.key_id == SigningKeyManager.from_material(key_material).key_id


def test_loads_from_key_file(tmp_path, key_material):
    path = tmp_path / "signing.key"
    path.write_text(key_material, encoding="utf-8")

    manager = SigningKeyManager.from_environment(env={ENV_SIGNING_KEY_FILE: str(path)})

    assert manager.key_id == SigningKeyManager.from_material(key_material).key_id


# -- key material must not leak -------------------------------------------

def test_repr_does_not_expose_private_material(key_material):
    manager = SigningKeyManager.from_material(key_material)
    rendered = f"{manager!r} {manager}"

    assert key_material not in rendered
    assert "REDACTED" in rendered
    assert manager.key_id in rendered


def test_manager_exposes_no_private_key_accessor(key_material):
    """Nothing public returns private bytes."""
    manager = SigningKeyManager.from_material(key_material)
    public_names = [n for n in dir(manager) if not n.startswith("_")]
    assert "private_key" not in public_names
    assert "private_key_bytes" not in public_names


def test_error_messages_do_not_echo_key_material():
    """A malformed value must not be reflected back into logs via the message."""
    secret_looking = "deadbeef" * 9  # wrong length, but plausible material
    with pytest.raises(SigningKeyError) as exc:
        SigningKeyManager.from_material(secret_looking)
    assert secret_looking not in str(exc.value)


# -- explicit rotation -----------------------------------------------------

def test_rotation_is_explicit_and_does_not_mutate(key_material):
    original = SigningKeyManager.from_material(key_material)
    original_id = original.key_id

    replacement = original.rotate_to(generate_private_key_hex())

    assert replacement.key_id != original_id
    # The running manager is untouched, so what it signed stays verifiable.
    assert original.key_id == original_id


# -- API dependency is fail-closed ----------------------------------------

def test_dependency_fails_closed_without_configuration(monkeypatch):
    monkeypatch.delenv(ENV_SIGNING_KEY, raising=False)
    monkeypatch.delenv(ENV_SIGNING_KEY_FILE, raising=False)

    with pytest.raises(HTTPException) as exc:
        dependencies.get_signing_key_manager()

    assert exc.value.status_code == 500
    assert exc.value.detail["error_code"] == "SIGNING_KEY_UNAVAILABLE"


def test_dependency_returns_configured_identity(monkeypatch, key_material):
    monkeypatch.delenv(ENV_SIGNING_KEY_FILE, raising=False)
    monkeypatch.setenv(ENV_SIGNING_KEY, key_material)

    manager = dependencies.get_signing_key_manager()

    assert manager.key_id == SigningKeyManager.from_material(key_material).key_id


def test_dependency_identity_is_stable_within_a_process(monkeypatch, key_material):
    monkeypatch.delenv(ENV_SIGNING_KEY_FILE, raising=False)
    monkeypatch.setenv(ENV_SIGNING_KEY, key_material)

    first = dependencies.get_signing_key_manager()
    second = dependencies.get_signing_key_manager()

    assert first is second
