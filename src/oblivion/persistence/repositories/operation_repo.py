"""Operation repository."""
from typing import Any

from sqlalchemy.orm import Session

from oblivion.persistence.models.operation import (
    OperationEventModel,
    OperationModel,
    TargetModel,
)


class OperationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_target(self, target_id: str, path: str, canonical_path: str, target_type: str, **kwargs: Any) -> TargetModel:
        target = TargetModel(
            id=target_id, path=path, canonical_path=canonical_path, target_type=target_type, **kwargs
        )
        self.session.add(target)
        self.session.flush()
        return target

    def get_target(self, target_id: str) -> TargetModel | None:
        return self.session.get(TargetModel, target_id)

    def create_operation(self, operation_id: str, target_id: str, mode: str, **kwargs: Any) -> OperationModel:
        op = OperationModel(id=operation_id, target_id=target_id, mode=mode, **kwargs)
        self.session.add(op)
        self.session.flush()
        return op

    def get_operation(self, operation_id: str) -> OperationModel | None:
        return self.session.get(OperationModel, operation_id)

    def append_event(self, event_id: str, operation_id: str, sequence: int, event_type: str, **kwargs: Any) -> OperationEventModel:
        ev = OperationEventModel(
            id=event_id, operation_id=operation_id, sequence=sequence, event_type=event_type, **kwargs
        )
        self.session.add(ev)
        self.session.flush()
        return ev

    def update_operation_state(self, operation_id: str, new_state: str) -> None:
        op = self.get_operation(operation_id)
        if op is not None:
            op.state = new_state
            self.session.flush()
