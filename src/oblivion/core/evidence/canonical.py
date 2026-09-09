"""Deprecated import compatibility shim for the canonical evidence codec.

There is exactly one implementation: :mod:`canonicalize`.
"""
from .canonicalize import canonical_hash, canonical_str, canonicalize

__all__ = ["canonical_hash", "canonical_str", "canonicalize"]
