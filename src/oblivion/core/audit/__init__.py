"""The authoritative audit log: who asked for what, when, and what the system did.

This package is distinct from ``core/evidence``, deliberately and permanently.

Evidence answers *what was observed about a target*. Audit answers *what acts
were performed against this system, by whom*. They are related - an audit entry
frequently names the evidence a step produced - but they are not
interchangeable, and a verifier must never be able to substitute one for the
other. ``core/audit/chain.py`` states that boundary in code.

The cryptographic model here is the *same* model Phase 23 established for
evidence, reused rather than reinvented: the one versioned canonicalizer
(``OBLIVION-CANON-1``), SHA-256 over canonical bytes, and a predecessor link
carrying the predecessor's digest. Building a second, weaker chaining scheme
beside the existing one would leave two things called "integrity" that mean
different amounts.
"""

from .chain import (
    AuditChainStatus,
    AuditChainVerification,
    AuditLinkResult,
    AuditLinkStatus,
    StoredAuditRecord,
    verify_audit_chain,
)
from .log import AuditAppendError, AuditLog, AuditQuery, append_independently
from .records import (
    AUDIT_SCHEMA_VERSION,
    ActorSource,
    AuditActor,
    AuditError,
    AuditEventType,
    AuditOutcome,
    AuditRecord,
    new_audit_id,
)

__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "ActorSource",
    "AuditActor",
    "AuditAppendError",
    "AuditChainStatus",
    "AuditChainVerification",
    "AuditError",
    "AuditEventType",
    "AuditLinkResult",
    "AuditLinkStatus",
    "AuditLog",
    "AuditOutcome",
    "AuditQuery",
    "AuditRecord",
    "StoredAuditRecord",
    "append_independently",
    "new_audit_id",
    "verify_audit_chain",
]
