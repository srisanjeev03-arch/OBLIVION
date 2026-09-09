
import pytest
from datetime import datetime
from oblivion.core.evidence.models import EvidencePackage
from oblivion.core.evidence.canonicalize import canonicalize

def test_evidence_canonicalization_stability():
    """Verify that canonicalization produces identical output for identical data."""
    now = datetime(2026, 9, 7, 12, 0, 0)
    data = {
        "operation_id": "op-123",
        "target_identity": "file-abc",
        "target_hash": "hash-xyz",
        "storage_profile": {"type": "ntfs"},
        "policy": {"mode": "COMPLETE_ERASURE"},
        "start_timestamp": now.isoformat(),
        "end_timestamp": now.isoformat(),
        "operation_results": {"status": "success"},
        "recovery_test_result": {"status": "success"},
        "residual_scan_result": {"status": "passed"},
        "assurance_result": {"status": "passed"},
        "warnings": [],
        "software_version": "1.0.0"
    }

    canonical_1 = canonicalize(data)
    canonical_2 = canonicalize(data)

    assert canonical_1 == canonical_2
    assert b'{"assurance_result":{"status":"passed"},' in canonical_1

def test_evidence_canonicalization_key_ordering():
    """Verify that key ordering is deterministic regardless of input dict order."""
    data_1 = {"a": 1, "b": 2}
    data_2 = {"b": 2, "a": 1}

    assert canonicalize(data_1) == canonicalize(data_2)
