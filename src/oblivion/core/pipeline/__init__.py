"""The Oblivion closed-loop operation pipeline.

DISCOVER → BASELINE → RECOMMEND → AUTHORIZE → ERASE → VALIDATE → TEST RECOVERY
→ ANALYZE RESIDUALS → ASSESS ASSURANCE → GENERATE EVIDENCE → ISSUE CERTIFICATE
→ VERIFY CERTIFICATE

See ``docs/OBLIVION_DOCUMENTATION.md §5`` for what each stage establishes and, just as
importantly, what it does not.
"""

from oblivion.core.pipeline.orchestrator import (
    ClosedLoopPipeline,
    PipelineRequest,
    PipelineResult,
    Stage,
    StageOutcome,
    StageStatus,
)

__all__ = [
    "ClosedLoopPipeline",
    "PipelineRequest",
    "PipelineResult",
    "Stage",
    "StageOutcome",
    "StageStatus",
]
