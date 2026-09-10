"""Oblivion's advisory AI layer.

Advisory means advisory: nothing in this package can delete, authorize, approve,
or set an outcome, and its import graph contains nothing that can. See
``docs/PHASE26_AI_BOUNDARY.md``.
"""

from oblivion.ai.advisor import SYSTEM_RULES, SecurityAdvisor
from oblivion.ai.provider import (
    AIProvider,
    LocalQwenProvider,
    NullProvider,
    ProviderError,
    StaticProvider,
    provider_from_env,
)
from oblivion.ai.schema import (
    FORBIDDEN_AUTHORITY_FIELDS,
    FORBIDDEN_OUTPUT_FIELDS,
    UNSAFE_CLAIM_PATTERNS,
    Advisory,
    AdvisoryError,
    AdvisoryKind,
    AdvisoryResult,
    AIStatus,
    ModelIdentity,
    SensitivityClass,
    find_unsafe_claims,
)
from oblivion.ai.validation import validate_advisory, validate_or_reject

__all__ = [
    "FORBIDDEN_AUTHORITY_FIELDS",
    "FORBIDDEN_OUTPUT_FIELDS",
    "SYSTEM_RULES",
    "UNSAFE_CLAIM_PATTERNS",
    "AIProvider",
    "AIStatus",
    "Advisory",
    "AdvisoryError",
    "AdvisoryKind",
    "AdvisoryResult",
    "LocalQwenProvider",
    "ModelIdentity",
    "NullProvider",
    "ProviderError",
    "SecurityAdvisor",
    "SensitivityClass",
    "StaticProvider",
    "find_unsafe_claims",
    "provider_from_env",
    "validate_advisory",
    "validate_or_reject",
]
