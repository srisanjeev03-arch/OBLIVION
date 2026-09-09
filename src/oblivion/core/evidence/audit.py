"""Audit event logging for Oblivion operations."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class AuditEvent:
    event_type: str
    operation_id: str
    timestamp: datetime
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "operation_id": self.operation_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }
