"""FastAPI dependencies and service singletons."""
import os
import tempfile
import uuid
from collections.abc import Callable, Generator
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.core.auth.passwords import hash_session_token
from oblivion.core.auth.rbac import has_permission
from oblivion.core.erasure.events import EngineEventEmitter
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.safety.paths import SafePathValidator
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.models.audit import AuditEventModel
from oblivion.persistence.models.operation import OperationEventModel
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.user_repo import UserRepository

# Global singleton Ed25519 signer instance for certificate issuance
_GLOBAL_SIGNER: Ed25519SignerVerifier | None = None



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



def get_signer() -> Ed25519SignerVerifier:
    """Provides singleton Ed25519 signer."""
    global _GLOBAL_SIGNER
    if _GLOBAL_SIGNER is None:
        _GLOBAL_SIGNER = Ed25519SignerVerifier.generate()
    return _GLOBAL_SIGNER


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

        # 2. Record audit event
        audit_event = AuditEventModel(
            id=f"audit_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            operation_id=operation_id,
            target_id=target_path,
            actor_id="system",
            outcome="OK",
            safe_metadata=str(details) if details else None,
        )
        self.session.add(audit_event)

        try:
            self.session.flush()
        except Exception:
            pass
