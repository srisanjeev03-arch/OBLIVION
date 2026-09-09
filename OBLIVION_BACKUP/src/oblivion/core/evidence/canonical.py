"""Deterministic canonicalization for Evidence Packages."""
import json
from typing import Any, Dict

def canonicalize(data: Dict[str, Any]) -> str:
    """
    Canonicalizes a dictionary into a deterministic JSON string.
    - Sorted keys.
    - No whitespace.
    - Consistent encoding.
    """
    return json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=True,
        separators=(',', ':'),
        default=str # Fallback for non-serializable types if any
    )
