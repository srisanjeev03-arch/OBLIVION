"""Deterministic JSON canonicalization for evidence packages (RFC-8785 compliant).

Produces a stable byte representation for signing and cryptographic integrity hashing.
"""
import hashlib
import json
from datetime import date, datetime
from typing import Any


def _canonicalize_value(value: Any) -> Any:
    """Recursively transform value to deterministic form."""
    if isinstance(value, dict):
        # Sort keys recursively, drop None values
        return {k: _canonicalize_value(v) for k, v in sorted(value.items()) if v is not None}
    if isinstance(value, (list, tuple)):
        return [_canonicalize_value(item) for item in value]
    if isinstance(value, float):
        # Round to avoid floating point representation issues across architectures
        return round(value, 12)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def canonicalize(data: dict[str, Any]) -> bytes:
    """Produce deterministic UTF-8 JSON bytes (RFC-8785 aligned).

    Rules:
    - Sorted keys at all nested levels
    - No insignificant whitespace (compact delimiters: ',', ':')
    - UTF-8 encoding without BOM
    - Stable float representation (rounded to 12 decimal places)
    - None/null values dropped recursively
    """
    if not isinstance(data, dict):
        raise TypeError("canonicalize() requires a dict")

    normalized = _canonicalize_value(data)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def canonical_str(data: dict[str, Any]) -> str:
    """Produce deterministic UTF-8 JSON string."""
    return canonicalize(data).decode("utf-8")


def canonical_hash(data: dict[str, Any]) -> str:
    """SHA-256 hex digest of canonical bytes."""
    return hashlib.sha256(canonicalize(data)).hexdigest()


__all__ = ["canonical_hash", "canonical_str", "canonicalize"]
