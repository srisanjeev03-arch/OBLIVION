"""Deterministic canonicalization for Evidence Packages.

This module is kept for backwards compatibility. The authoritative
implementation lives in :mod:`oblivion.core.evidence.canonicalize`.
"""
from oblivion.core.evidence.canonicalize import canonical_hash, canonicalize

__all__ = ["canonicalize", "canonical_hash"]