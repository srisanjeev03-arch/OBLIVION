"""Deterministic JSON canonicalization for evidence packages.

Produces a stable byte representation for signing/hashing.
"""
import json
from typing import Any, Dict


def _canonicalize_value(value: Any) -> Any:
    """Recursively transform value to deterministic form."""
    if isinstance(value, dict):
        # Sort keys recursively, drop None values
        return {k: _canonicalize_value(v) for k, v in sorted(value.items()) if v is not None}
    if isinstance(value, (list, tuple)):
        return [_canonicalize_value(item) for item in value]
    if isinstance(value, float):
        # Round to avoid floating point representation issues
        return round(value, 12)
    return value


def canonicalize(data: Dict[str, Any]) -> bytes:
    """Produce deterministic UTF-8 JSON bytes.

    - Sorted keys at all levels
    - No insignificant whitespace
    - UTF-8 encoding
    - Stable float representation
    - None values dropped
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
    ).encode("utf-8")


def canonical_hash(data: Dict[str, Any]) -> str:
    """SHA-256 hex digest of canonical bytes."""
    import hashlib
    return hashlib.sha256(canonicalize(data)).hexdigest()
