"""Evidence repository."""
from typing import Optional, Any
from sqlalchemy.orm import Session
from oblivion.persistence.models.evidence import (
    BaselineModel,
    RecoveryTestModel,
    ResidualFindingModel,
    AssuranceResultModel,
)


class EvidenceRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_baseline(self, baseline_id: str, operation_id: str, target_id: str, **kwargs: Any) -> BaselineModel:
        b = BaselineModel(id=baseline_id, operation_id=operation_id, target_id=target_id, **kwargs)
        self.session.add(b)
        self.session.flush()
        return b

    def create_recovery_test(self, test_id: str, operation_id: str, result_status: str, **kwargs: Any) -> RecoveryTestModel:
        rt = RecoveryTestModel(id=test_id, operation_id=operation_id, result_status=result_status, **kwargs)
        self.session.add(rt)
        self.session.flush()
        return rt

    def create_residual_finding(self, finding_id: str, operation_id: str, severity: str, description: str, **kwargs: Any) -> ResidualFindingModel:
        f = ResidualFindingModel(
            id=finding_id, operation_id=operation_id, severity=severity, description=description, **kwargs
        )
        self.session.add(f)
        self.session.flush()
        return f

    def create_assurance_result(self, result_id: str, operation_id: str, status: str, confidence: str, **kwargs: Any) -> AssuranceResultModel:
        a = AssuranceResultModel(
            id=result_id, operation_id=operation_id, status=status, confidence=confidence, **kwargs
        )
        self.session.add(a)
        self.session.flush()
        return a

    def get_assurance_result(self, operation_id: str) -> Optional[AssuranceResultModel]:
        return self.session.query(AssuranceResultModel).filter_by(operation_id=operation_id).one_or_none()
