"""Authentication API endpoints."""
import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import (
    extract_token_from_header,
    get_current_user,
    get_db,
)
from oblivion.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserOut,
)
from oblivion.core.audit import (
    AuditActor,
    AuditEventType,
    AuditLog,
    AuditOutcome,
    append_independently,
)
from oblivion.core.auth.passwords import (
    generate_session_token,
    hash_session_token,
    verify_password,
)
from oblivion.core.auth.rbac import get_role_permissions
from oblivion.persistence.database import get_session_factory
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.user_repo import UserRepository

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Default session duration: 24 hours
SESSION_DURATION_HOURS = 24


def _record_failed_login(username: str, reason: str) -> None:
    """Record a rejected sign-in in a transaction of its own.

    The request is about to raise 401, and `get_db` rolls back on the way out.
    An entry written into that transaction would be rolled back with it, so the
    log would fall silent about exactly the events that matter most for
    detecting credential stuffing. It is committed separately instead.

    Only the *claimed* username is recorded, marked UNAUTHENTICATED. The
    submitted password never appears: a failed attempt is frequently a mistyped
    *valid* password for another account, so logging it would turn the audit
    trail into a credential dump.
    """
    append_independently(
        get_session_factory(),
        AuditEventType.AUTH_LOGIN_FAILED,
        AuditOutcome.REFUSED,
        AuditActor.unauthenticated(username),
        summary="Sign-in refused.",
        safe_metadata={"reason": reason},
    )


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Authenticates a user and issues an opaque server-side session token."""
    repo = UserRepository(db)
    # Ensure bootstrap admin exists on first login attempt if needed
    repo.bootstrap_admin_if_needed()

    user = repo.get_by_username(request.username)
    if not user or user.disabled or not user.password_hash:
        # One message for every rejection, so the response cannot be used to
        # discover which usernames exist - but the audit log keeps the real
        # reason, where only an auditor can read it.
        _record_failed_login(
            request.username,
            "no such user, account disabled, or no password set",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_CREDENTIALS", "message": "Invalid username or password"},
        )

    if not verify_password(request.password, user.password_hash):
        _record_failed_login(request.username, "password did not match")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_CREDENTIALS", "message": "Invalid username or password"},
        )

    # Generate cryptographically secure session token
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=SESSION_DURATION_HOURS)

    # Store only token hash
    repo.create_session(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
    user.last_authenticated_at = datetime.datetime.now(datetime.UTC)
    db.flush()

    roles = repo.get_user_role_names(user.id)
    permissions = list(get_role_permissions(roles))

    user_out = UserOut(
        id=user.id,
        username=user.username,
        roles=roles,
        permissions=permissions,
        disabled=user.disabled,
        created_at=user.created_at,
        last_authenticated_at=user.last_authenticated_at,
    )

    # Shares this request's transaction: if the session insert above were to
    # fail, the log must not claim a sign-in that never completed.
    AuditLog(db).append(
        AuditEventType.AUTH_LOGIN_SUCCEEDED,
        AuditOutcome.SUCCEEDED,
        AuditActor.authenticated(user.id, ",".join(sorted(roles)) if roles else "NONE"),
        summary="Signed in.",
        safe_metadata={"session_expires_at": expires_at.isoformat()},
    )

    return LoginResponse(
        access_token=raw_token,
        token_type="bearer",
        expires_at=expires_at,
        user=user_out,
    )


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    """Revokes the active session token."""
    raw_token = extract_token_from_header(authorization)
    if not raw_token:
        # Also check custom header or cookie
        raw_token = request.headers.get("X-Session-Token")

    if raw_token:
        token_hash = hash_session_token(raw_token)
        repo = UserRepository(db)
        # Resolve who is signing out *before* revoking, so the entry names the
        # principal rather than recording an anonymous revocation.
        session_model = repo.get_session_by_token_hash(token_hash)
        repo.revoke_session(token_hash)
        db.flush()

        if session_model is not None:
            roles = repo.get_user_role_names(session_model.user_id)
            AuditLog(db).append(
                AuditEventType.AUTH_LOGOUT,
                AuditOutcome.SUCCEEDED,
                AuditActor.authenticated(
                    session_model.user_id, ",".join(sorted(roles)) if roles else "NONE"
                ),
                summary="Signed out; session revoked.",
            )

    return LogoutResponse(
        status="COMPLETED",
        message="Session successfully terminated",
    )


@router.get("/me", response_model=UserOut, status_code=status.HTTP_200_OK)
async def get_current_user_profile(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """Returns the profile and granted permissions of the authenticated user."""
    repo = UserRepository(db)
    roles = repo.get_user_role_names(current_user.id)
    permissions = list(get_role_permissions(roles))

    return UserOut(
        id=current_user.id,
        username=current_user.username,
        roles=roles,
        permissions=permissions,
        disabled=current_user.disabled,
        created_at=current_user.created_at,
        last_authenticated_at=current_user.last_authenticated_at,
    )
