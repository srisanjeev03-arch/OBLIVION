"""Audit repository."""
from typing import Any

from sqlalchemy.orm import Session

from oblivion.persistence.models.audit import AuditEventModel


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def append(self, event_id: str, event_type: str, outcome: str, **kwargs: Any) -> AuditEventModel:
        ev = AuditEventModel(id=event_id, event_type=event_type, outcome=outcome, **kwargs)
        self.session.add(ev)
        self.session.flush()
        return ev
