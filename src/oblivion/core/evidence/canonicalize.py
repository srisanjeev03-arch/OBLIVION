"""The authoritative canonical byte form for everything Oblivion signs.

There is exactly one implementation. ``canonical.py`` re-exports from here and
adds nothing; nothing else in the tree may define a second one, because two
canonicalizations mean two different answers to "is this signature valid?".

## The contract: OBLIVION-CANON-1

Aligned with RFC 8785 (JSON Canonicalization Scheme), with the deviations listed
below stated rather than glossed over:

* object keys sorted by UTF-16 code unit, as RFC 8785 requires (not by Python's
  default code-point order, which differs above the BMP);
* no insignificant whitespace; ``,`` and ``:`` separators;
* UTF-8 output, no BOM;
* ``null`` is **preserved**;
* NaN and Infinity are rejected rather than emitted;
* integers are emitted exactly; floats use Python's shortest round-trip repr,
  normalised toward the ECMAScript form.

### Deviation from RFC 8785, stated plainly

Full RFC 8785 number serialisation is the ECMAScript ``Number::toString``
algorithm. This implementation reproduces it for the values Oblivion actually
signs - integers, and floats that round-trip through ``repr`` - but does not
implement every exponent-formatting edge case of ES6. Evidence in this system
carries integers, ISO-8601 strings and digests; a float reaching this function
is unusual. Rather than claim conformance it does not have, the format is named
``OBLIVION-CANON-1`` and every signed artifact records which version produced
it, so a future strict-JCS codec can be added as ``OBLIVION-CANON-2`` without
invalidating anything already signed.

### Why nulls are preserved

An earlier revision dropped ``None`` values recursively. That made
``{"a": 1, "b": null}`` and ``{"a": 1}`` produce identical bytes, so two
semantically different evidence packages shared one digest - a collision an
attacker can steer. Dropping a key is a change to the data, and the canonical
form must reflect it.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any

#: Identifies the canonical byte form. Every signed artifact records this, so a
#: future codec change cannot silently reinterpret an existing signature.
CANONICALIZATION_VERSION = "OBLIVION-CANON-1"

#: Versions this build can verify.
SUPPORTED_CANONICALIZATION_VERSIONS: frozenset[str] = frozenset({CANONICALIZATION_VERSION})


class CanonicalizationError(ValueError):
    """Raised when a value has no deterministic canonical representation."""


class _FloatLiteral(float):
    """Carries an already-formatted numeric literal through ``json.dumps``."""

    _literal: str

    def __new__(cls, literal: str) -> _FloatLiteral:
        obj = super().__new__(cls, float(literal))
        obj._literal = literal
        return obj

    def __repr__(self) -> str:
        return self._literal


def _sort_key(key: str) -> bytes:
    """RFC 8785 orders keys by UTF-16 code unit, not by code point."""
    return key.encode("utf-16-be", errors="surrogatepass")


def _format_float(value: float) -> str:
    if math.isnan(value) or math.isinf(value):
        raise CanonicalizationError(
            "NaN and Infinity have no canonical JSON representation"
        )
    if value == int(value) and abs(value) < 1e16:
        # ECMAScript renders integral doubles without a fractional part.
        return str(int(value))
    return repr(value)


def _normalize(value: Any) -> Any:
    """Reduce a value to the small set the encoder can emit deterministically.

    Rejects anything it cannot represent faithfully rather than coercing it with
    ``str()``. Silent coercion is how two different objects end up sharing a
    digest.
    """
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return _FloatLiteral(_format_float(value))
    if isinstance(value, (datetime, date)):
        # Timestamps are canonicalised as ISO-8601 text. Callers that need a
        # specific offset must normalise before calling.
        return value.isoformat()
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise CanonicalizationError(
                    f"Object keys must be strings; got {type(k).__name__}"
                )
            out[k] = _normalize(v)
        return {k: out[k] for k in sorted(out, key=_sort_key)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    raise CanonicalizationError(
        f"{type(value).__name__} has no canonical representation; convert it "
        "explicitly before canonicalizing"
    )


def canonicalize(data: dict[str, Any]) -> bytes:
    """Produce the canonical UTF-8 bytes for ``data``.

    Deterministic: the same semantic input always yields the same bytes, in this
    process and any other.
    """
    if not isinstance(data, dict):
        raise CanonicalizationError("canonicalize() requires a dict at the top level")

    normalized = _normalize(data)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=False,  # ordering already applied with UTF-16 collation
    ).encode("utf-8")


def canonical_str(data: dict[str, Any]) -> str:
    """The canonical form as text."""
    return canonicalize(data).decode("utf-8")


def canonical_hash(data: dict[str, Any]) -> str:
    """Lowercase hex SHA-256 of the canonical bytes."""
    return hashlib.sha256(canonicalize(data)).hexdigest()


def digest_bytes(payload: bytes) -> str:
    """Lowercase hex SHA-256 of raw bytes."""
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "CANONICALIZATION_VERSION",
    "SUPPORTED_CANONICALIZATION_VERSIONS",
    "CanonicalizationError",
    "canonical_hash",
    "canonical_str",
    "canonicalize",
    "digest_bytes",
]
