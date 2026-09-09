"""Typed models for Evidence Packages."""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

@dataclass
class EvidencePackage:
    operation_id: str
    target_identity: str
    target_hash: str
    storage_profile: Dict[str, Any]
    policy: Dict[str, Any]
    start_timestamp: datetime
    end_timestamp: datetime
    operation_results: Dict[str, Any]
    recovery_test_result: Dict[str, Any]
    residual_scan_result: Dict[str, Any]
    assurance_result: Dict[str, Any]
    warnings: List[Dict[str, Any]]
    software_version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for canonicalization."""
        return {
            "operation_id": self.operation_id,
            "target_identity": self.target_identity,
            "target_hash": self.target_hash,
            "storage_profile": self.storage_profile,
            "policy": self.policy,
            "start_timestamp": self.start_timestamp.isoformat(),
            "end_timestamp": self.end_timestamp.isoformat(),
            "operation_results": self.operation_results,
            "recovery_test_result": self.recovery_test_result,
            "residual_scan_result": self.residual_scan_result,
            "assurance_result": self.assurance_result,
            "warnings": self.warnings,
            "software_version": self.software_version,
        }
