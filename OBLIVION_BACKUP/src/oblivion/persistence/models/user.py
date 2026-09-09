"""User, Role, Permission, Session models."""
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from oblivion.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    last_authenticated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    roles: Mapped[List["RoleModel"]] = relationship(
        secondary="role_permissions",
        back_populates="users",
        overlaps="permissions,users",
    )
    sessions: Mapped[List["SessionModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RoleModel(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    permissions: Mapped[List["PermissionModel"]] = relationship(
        secondary="role_permissions",
        back_populates="roles",
        overlaps="roles,users",
    )
    users: Mapped[List["UserModel"]] = relationship(
        secondary="role_permissions",
        back_populates="roles",
        overlaps="permissions,roles",
    )


class PermissionModel(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    roles: Mapped[List["RoleModel"]] = relationship(
        secondary="role_permissions",
        back_populates="permissions",
        overlaps="permissions,users",
    )


class RolePermissionModel(Base):
    """Association table linking roles, permissions, and users."""
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_id: Mapped[str] = mapped_column(String(64), ForeignKey("roles.id"), nullable=False, index=True)
    permission_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("permissions.id"), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("users.id"), index=True)


class SessionModel(Base):
    """Server-side session record. No secrets stored in plaintext."""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Only a token hash is stored, never the raw token
    token_hash: Mapped[Optional[str]] = mapped_column(String(128))

    user: Mapped["UserModel"] = relationship(back_populates="sessions")
