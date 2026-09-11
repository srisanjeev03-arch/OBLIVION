"""Operation repository."""
from typing import Any

from sqlalchemy import func, select
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

    def list_operations(
        self,
        *,
        state: str | None = None,
        operation_id: str | None = None,
        requested_by: str | None = None,
        target_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[OperationModel], int]:
        """Persisted operations, newest first, with the total before paging.

        Filtering happens in the database rather than in the route. A route that
        fetched everything and filtered in Python would still have *read* every
        operation, which is the wrong shape for a record an auditor relies on -
        and it would degrade badly as the table grows.

        The total is returned alongside the page so a caller can tell "this is
        page one of many" from "this is everything", without inferring it from a
        full page.
        """
        conditions = []
        if state:
            conditions.append(OperationModel.state == state)
        if operation_id:
            conditions.append(OperationModel.id == operation_id)
        if requested_by:
            conditions.append(OperationModel.requested_by == requested_by)
        if target_id:
            conditions.append(OperationModel.target_id == target_id)

        total_stmt = select(func.count()).select_from(OperationModel)
        page_stmt = select(OperationModel)
        for condition in conditions:
            total_stmt = total_stmt.where(condition)
            page_stmt = page_stmt.where(condition)

        total = int(self.session.execute(total_stmt).scalar_one())
        page_stmt = (
            page_stmt.order_by(
                OperationModel.created_at.desc(), OperationModel.id.desc()
            )
            .offset(max(0, offset))
            .limit(max(1, limit))
        )
        rows = list(self.session.execute(page_stmt).scalars().all())
        return rows, total

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
