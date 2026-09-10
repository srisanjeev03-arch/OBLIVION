"""API route modules."""
from .auth import router as auth_router
from .certificates import router as certificates_router
from .evidence import router as evidence_router
from .operations import router as operations_router
from .pipeline import router as pipeline_router
from .recovery import router as recovery_router
from .targets import router as targets_router

__all__ = [
    "auth_router",
    "certificates_router",
    "evidence_router",
    "operations_router",
    "pipeline_router",
    "recovery_router",
    "targets_router",
]

