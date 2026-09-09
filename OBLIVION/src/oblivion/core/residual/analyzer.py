import logging
from pathlib import Path
from typing import Dict, Any, List
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.state.machine import OperationStateMachine, State
from oblivion.core.erasure.events import EngineEventEmitter
from .models import ResidualStatus, ResidualEvidence, EvidenceType
from .detectors import ResidualDetector, FileSystemResidualDetector

logger = logging.getLogger(__name__)

class ResidualAnalyzer:
    def __init__(self, validator: SafePathValidator, event_emitter: EngineEventEmitter):
        self.validator = validator
        self.event_emitter = event_emitter
        self.state_machine = OperationStateMachine()
        self.detectors: List[ResidualDetector] = [FileSystemResidualDetector()]

    def analyze(self, operation_id: str, baseline: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrates residual analysis."""
        self.state_machine.transition_to(State.ANALYZING)
        target_path = Path(baseline["path"])
        self.event_emitter.emit("RESIDUAL_ANALYSIS_STARTED", operation_id, str(target_path), {})

        self.state_machine.transition_to(State.RESIDUAL_ANALYSIS)

        all_evidence: List[ResidualEvidence] = []
        for detector in self.detectors:
            all_evidence.extend(detector.detect(baseline, target_path))

        # Classification
        status = ResidualStatus.NO_RESIDUAL_DETECTED
        if any(e.evidence_type in [EvidenceType.FILE_PRESENT, EvidenceType.DIRECTORY_REMAINS] for e in all_evidence):
            status = ResidualStatus.RESIDUAL_DETECTED

        self.state_machine.transition_to(State.VERIFYING)
        self.event_emitter.emit("RESIDUAL_ANALYSIS_COMPLETED", operation_id, str(target_path), {"status": status.name})
        self.state_machine.transition_to(State.COMPLETED)

        return {
            "status": status.name,
            "evidence": [{"evidence_type": e.evidence_type.name, "explanation": e.explanation, "artifact_path": e.artifact_path} for e in all_evidence]
        }
