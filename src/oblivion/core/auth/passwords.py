"""Argon2id password hashing and opaque session token cryptography."""
import base64
import hashlib
import os
import secrets

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

# Default Argon2id parameters (OWASP / RFC 9106 recommended minimums)
DEFAULT_MEMORY_COST = 65536  # 64 MiB
DEFAULT_ITERATIONS = 3
DEFAULT_LANES = 4
DEFAULT_KEY_LEN = 32
DEFAULT_SALT_LEN = 16


def hash_password(
    password: str,
    memory_cost: int = DEFAULT_MEMORY_COST,
    iterations: int = DEFAULT_ITERATIONS,
    lanes: int = DEFAULT_LANES,
    salt: bytes | None = None,
) -> str:
    """Derives an Argon2id hash for the given password."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")

    actual_salt = salt if salt is not None else os.urandom(DEFAULT_SALT_LEN)
    kdf = Argon2id(
        salt=actual_salt,
        length=DEFAULT_KEY_LEN,
        iterations=iterations,
        lanes=lanes,
        memory_cost=memory_cost,
    )
    derived = kdf.derive(password.encode("utf-8"))

    salt_b64 = base64.b64encode(actual_salt).decode("ascii")
    key_b64 = base64.b64encode(derived).decode("ascii")

    return f"$argon2id$v=19$m={memory_cost},t={iterations},p={lanes}${salt_b64}${key_b64}"


def verify_password(password: str, hashed_password: str | None) -> bool:
    """Verifies a password against an Argon2id formatted string. Timing-safe."""
    if not password or not hashed_password:
        return False

    try:
        parts = hashed_password.split("$")
        # Format: ['', 'argon2id', 'v=19', 'm=65536,t=3,p=4', salt_b64, key_b64]
        if len(parts) != 6 or parts[1] != "argon2id":
            return False

        params_str = parts[3]
        params = dict(item.split("=") for item in params_str.split(","))
        memory_cost = int(params["m"])
        iterations = int(params["t"])
        lanes = int(params["p"])

        salt = base64.b64decode(parts[4])
        expected_key = base64.b64decode(parts[5])

        kdf = Argon2id(
            salt=salt,
            length=len(expected_key),
            iterations=iterations,
            lanes=lanes,
            memory_cost=memory_cost,
        )
        kdf.verify(password.encode("utf-8"), expected_key)
        return True
    except Exception:
        return False


def generate_session_token() -> str:
    """Generates a cryptographically secure, opaque random session token."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Computes the SHA-256 hex digest of a session token for storage and indexing."""
    if not token:
        raise ValueError("Session token cannot be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
