"""Audit event logging for Oblivion operations."""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

@dataclass
class AuditEvent:
    event_type: str
    operation_id: str
    timestamp: datetime
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "operation_id": self.operation_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }
