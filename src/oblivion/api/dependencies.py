"""FastAPI dependencies and service singletons."""
import os
import tempfile
import uuid
from collections.abc import Callable, Generator
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from oblivion.certificate.keys import SigningKeyError, SigningKeyManager
from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.certificate.trust_model import (
    TrustStore,
    TrustStoreError,
    load_trust_store_from_env,
)
from oblivion.core.audit import (
    AuditActor,
    AuditEventType,
    AuditLog,
    AuditOutcome,
)
from oblivion.core.auth.passwords import hash_session_token
from oblivion.core.auth.rbac import has_permission
from oblivion.core.erasure.events import EngineEventEmitter
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.safety.paths import SafePathValidator
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.models.operation import OperationEventModel
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.user_repo import UserRepository
from oblivion.privileged.client import PrivilegedClient
from oblivion.privileged.service import (
    ReplayCache,
    RequestAuthenticator,
    build_service_from_env,
)
from oblivion.privileged.transport import (
    InProcessTransport,
    NamedPipeTransport,
    Transport,
)

# The configured signing identity, resolved once per process. It is *loaded*,
# never generated: see oblivion.certificate.keys for why implicit generation is
# unsafe for a system that issues verifiable certificates.
_SIGNING_KEY_MANAGER: SigningKeyManager | None = None



def get_db() -> Generator[Session, None, None]:
    """Database session generator."""
    init_db()
    session_factory = get_session_factory()
    with session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def extract_token_from_header(authorization: str | None) -> str | None:
    """Extracts raw bearer token from Authorization header string."""
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    if len(parts) == 1:
        return parts[0]
    return None


def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> UserModel:
    """
    Authenticates current user via server-side session token digest.
    Returns UserModel or raises 401 Unauthorized.
    """
    token = extract_token_from_header(authorization)
    if not token:
        # Check custom session header
        token = request.headers.get("X-Session-Token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHENTICATED", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_hash = hash_session_token(token)
    repo = UserRepository(db)
    session_model = repo.get_session_by_token_hash(token_hash)

    if not session_model or session_model.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "SESSION_INVALID", "message": "Invalid or expired session token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = repo.get_by_id(session_model.user_id)
    if not user or user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "USER_DISABLED", "message": "User account is disabled or inactive"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_permission(required_permission: str) -> Callable[..., UserModel]:
    """
    Dependency factory that verifies the current user has the required permission.
    Returns user on success, raises 403 Forbidden on failure.
    """
    def _permission_guard(
        current_user: UserModel = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> UserModel:
        repo = UserRepository(db)
        roles = repo.get_user_role_names(current_user.id)
        if not has_permission(roles, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FORBIDDEN",
                    "message": f"Insufficient permissions: requires '{required_permission}'",
                },
            )
        return current_user

    return _permission_guard


def resolve_audit_actor(user: UserModel, db: Session) -> AuditActor:
    """Build an audit actor from an *already authenticated* principal.

    The only inputs are the ``UserModel`` that ``get_current_user`` resolved
    from a server-side session record, and that user's roles read from the
    database. Nothing here reads the request, so there is no path by which a
    body field, header or query parameter can decide who an act is attributed
    to.

    Multiple roles are recorded joined and sorted rather than reduced to one.
    Picking a single "primary" role would need a precedence rule this system
    does not define, and inventing one would make the audit record state
    something the authorization model never decided.
    """
    roles = UserRepository(db).get_user_role_names(user.id)
    label = ",".join(sorted(roles)) if roles else "NONE"
    return AuditActor.authenticated(user.id, label)


def require_role(required_role: str) -> Callable[..., UserModel]:
    """
    Dependency factory that verifies the current user has the required role name.
    """
    def _role_guard(
        current_user: UserModel = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> UserModel:
        repo = UserRepository(db)
        roles = [r.upper() for r in repo.get_user_role_names(current_user.id)]
        if required_role.upper() not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FORBIDDEN",
                    "message": f"Insufficient role: requires '{required_role}'",
                },
            )
        return current_user

    return _role_guard



def get_safe_validator() -> SafePathValidator:
    """Provides path safety validator."""
    allowed = os.environ.get("OBLIVION_ALLOWED_ROOTS")
    if allowed:
        roots = [r.strip() for r in allowed.split(os.pathsep) if r.strip()]
        return SafePathValidator(allowed_roots=roots)
    return SafePathValidator()


def get_vault_key() -> bytes:
    """
    Returns the configured vault AES-256 key.
    Fails closed with HTTPException 500 (VAULT_KEY_UNAVAILABLE / VAULT_KEY_INVALID) if not properly configured.
    """
    env_key = os.environ.get("OBLIVION_VAULT_KEY")
    if not env_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "VAULT_KEY_UNAVAILABLE",
                "message": "Vault encryption key is not configured in environment (fail-closed)",
            },
        )

    try:
        key_bytes = bytes.fromhex(env_key)
        if len(key_bytes) == 32:
            return key_bytes
    except ValueError:
        if len(env_key.encode("utf-8")) == 32:
            return env_key.encode("utf-8")

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "VAULT_KEY_INVALID",
            "message": "OBLIVION_VAULT_KEY must be a valid 32-byte key (64 hex characters)",
        },
    )


def get_recovery_vault(
    validator: SafePathValidator = Depends(get_safe_validator),
    key: bytes = Depends(get_vault_key),
) -> RecoveryVault:
    """Provides RecoveryVault instance with fail-closed key validation."""
    vault_dir = os.environ.get("OBLIVION_VAULT_DIR")
    if not vault_dir:
        vault_dir = os.path.join(tempfile.gettempdir(), "oblivion_vault")
    os.makedirs(vault_dir, exist_ok=True)
    return RecoveryVault(vault_root=vault_dir, validator=validator, key=key)



def get_signing_key_manager() -> SigningKeyManager:
    """Returns the configured signing identity.

    Fail-closed, in the same shape as ``get_vault_key``: a deployment with no
    configured key cannot sign, and says so, rather than minting a throwaway
    identity that would invalidate every certificate it had already issued.
    ``SigningKeyError`` messages describe the shape of the problem and never
    contain key material, so this is safe to surface.
    """
    global _SIGNING_KEY_MANAGER
    if _SIGNING_KEY_MANAGER is None:
        try:
            _SIGNING_KEY_MANAGER = SigningKeyManager.from_environment()
        except SigningKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "SIGNING_KEY_UNAVAILABLE", "message": str(exc)},
            )
    return _SIGNING_KEY_MANAGER


def reset_signing_key_manager() -> None:
    """Drops the cached identity so a new configuration can be loaded.

    Used by tests to simulate a process restart; production reloads by
    restarting the service.
    """
    global _SIGNING_KEY_MANAGER
    _SIGNING_KEY_MANAGER = None


def get_signer(
    manager: SigningKeyManager = Depends(get_signing_key_manager),
) -> Ed25519SignerVerifier:
    """Provides a signer bound to the configured, persistent identity."""
    return manager.signer()


def get_trust_store() -> TrustStore:
    """The trust anchors this deployment recognises.

    Resolved per request from configuration rather than cached, so rotating a
    trust anchor takes effect without a restart. An unconfigured deployment gets
    a ``NullTrustStore``: no signer is trusted, ``SIGNER_TRUST`` reports
    ``NOT_CHECKED``, and verification lands on ``INCONCLUSIVE``. That is the
    correct posture - a certificate must never become trusted merely because it
    carries a key that verifies its own signature.

    Malformed configuration fails closed rather than silently trusting nothing,
    because a typo in a trust anchor would otherwise look identical to a
    deliberately unconfigured deployment.
    """
    try:
        return load_trust_store_from_env()
    except TrustStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "TRUST_STORE_INVALID", "message": str(exc)},
        )


def get_replay_cache(request: Request) -> ReplayCache:
    """The application's nonce cache.

    Raises rather than quietly creating one. A missing cache would mean the app
    was built by something other than ``create_app`` - and silently handing back
    a fresh cache would restore exactly the defect M-1 describes, while looking
    like it worked.
    """
    cache = getattr(request.app.state, "privileged_replay_cache", None)
    if not isinstance(cache, ReplayCache):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "REPLAY_CACHE_UNAVAILABLE",
                "message": (
                    "No application-scoped replay cache is configured, so replay "
                    "protection could not be enforced. Refusing rather than "
                    "proceeding without it."
                ),
            },
        )
    return cache


def get_privileged_client(
    request: Request,
    validator: SafePathValidator = Depends(get_safe_validator),
) -> PrivilegedClient:
    """The handle on the privileged service, or a clear 503.

    The service object is rebuilt per request - it is cheap, and its validator
    must reflect current configuration - but the **nonce cache is not**. It is
    taken from ``app.state``, where it lives for the life of the application.

    That split is the fix for audit finding M-1: this dependency previously let
    each request's service construct its own cache, so every request started
    with an empty one and no nonce was ever seen twice. Replay protection is
    only a control if the memory outlives the request being checked.

    Two transports, chosen by configuration rather than guessed:

    * ``OBLIVION_PRIVILEGED_PIPE`` set - talk to a privileged host over its
      named pipe. This is the deployment posture, and the only one that provides
      real process isolation.
    * unset - run the service in this process. Honest for development, and the
      client reports ``isolated == False`` so nothing can mistake it for the
      real boundary.

    Without ``OBLIVION_IPC_KEY`` there is no way to authenticate a request, and
    this raises 503 rather than inventing a key. A default secret would be
    indistinguishable from no authentication at all, and a deployment that
    forgot to configure IPC must fail loudly.
    """
    authenticator = RequestAuthenticator.from_env()
    if authenticator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "PRIVILEGED_SERVICE_UNAVAILABLE",
                "message": (
                    "OBLIVION_IPC_KEY is not configured, so privileged operations "
                    "cannot be authenticated and will not be attempted."
                ),
            },
        )

    pipe_name = os.environ.get("OBLIVION_PRIVILEGED_PIPE")
    transport: Transport
    if pipe_name:
        # The privileged host owns its own long-lived service and cache; this
        # process only speaks to it.
        transport = NamedPipeTransport(pipe_name)
    else:
        transport = InProcessTransport(
            build_service_from_env(
                validator, replay_cache=get_replay_cache(request)
            )
        )

    return PrivilegedClient(transport, authenticator)


def _safe_engine_metadata(
    event_type: str, details: dict[str, Any] | None
) -> dict[str, Any]:
    """Reduce engine event details to values the canonicalizer can encode.

    The canonicalizer refuses types it cannot represent deterministically
    rather than coercing them, which is right for evidence but would turn an
    ordinary engine event into a failed request here. Values are therefore
    narrowed to JSON primitives at this boundary, and anything else is recorded
    as its string form with the conversion made visible in the key name, so a
    reader is never left believing a stringified object was the original value.
    """
    safe: dict[str, Any] = {"engine_event_type": event_type}
    for key, value in (details or {}).items():
        if value is None or isinstance(value, bool | int | float | str):
            safe[key] = value
        else:
            safe[f"{key}_repr"] = str(value)
    return safe


class DatabaseEventEmitter(EngineEventEmitter):
    """Engine event emitter that persists events to SQLite/SQLAlchemy."""

    def __init__(self, session: Session):
        self.session = session
        self._seq = 0

    def emit(self, event_type: str, operation_id: str, target_path: str, details: dict[str, Any] | None = None) -> None:
        super().emit(event_type, operation_id, target_path, details)
        self._seq += 1
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        from_state = details.get("from_state") if details else None
        to_state = (details.get("state") or details.get("to_state")) if details else None

        # 1. Record operation event
        op_event = OperationEventModel(
            id=event_id,
            operation_id=operation_id,
            sequence=self._seq,
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            payload=str(details) if details else None,
        )

        self.session.add(op_event)

        # 2. Record the act in the authoritative audit log.
        #
        # The previous revision wrote a row here with `actor_id="system"` and
        # `outcome="OK"` hard-coded, metadata as a Python repr, and a bare
        # `except Exception: pass` around the flush. Every one of those made the
        # log less able to answer the question it exists for: the actor was a
        # constant, the outcome was a constant, the metadata could not be parsed
        # back, and a write that failed left no trace of having failed.
        #
        # The engine genuinely has no human principal to name - it is the
        # application acting on its own behalf - so the actor is recorded as
        # SYSTEM and marked as such, rather than borrowing an identity it cannot
        # substantiate. The human who authorized the operation is recorded
        # separately, by the route that took their authenticated request.
        AuditLog(self.session).append(
            AuditEventType.OPERATION_STATE_CHANGED,
            AuditOutcome.SUCCEEDED,
            AuditActor.system("erasure_engine"),
            operation_id=operation_id,
            target_identity=target_path,
            summary=f"Engine event {event_type}.",
            safe_metadata=_safe_engine_metadata(event_type, details),
        )

        self.session.flush()
