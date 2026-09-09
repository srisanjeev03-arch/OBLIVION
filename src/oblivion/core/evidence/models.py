"""Typed models for Evidence Packages."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class EvidencePackage:
    operation_id: str
    target_identity: str
    target_hash: str
    storage_profile: dict[str, Any]
    policy: dict[str, Any]
    start_timestamp: datetime
    end_timestamp: datetime
    operation_results: dict[str, Any]
    recovery_test_result: dict[str, Any]
    residual_scan_result: dict[str, Any]
    assurance_result: dict[str, Any]
    warnings: list[dict[str, Any]]
    software_version: str

    def to_dict(self) -> dict[str, Any]:
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
