"""User and RBAC repository."""
import datetime
import os
import uuid

from sqlalchemy.orm import Session

from oblivion.core.auth.passwords import hash_password
from oblivion.core.auth.rbac import ALL_PERMISSIONS, ROLE_PERMISSIONS, Role
from oblivion.persistence.models.user import (
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    SessionModel,
    UserModel,
)


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def init_default_roles_and_permissions(self) -> None:
        """Seeds the 5 default roles and permissions if they do not exist."""
        # 1. Create Permissions
        existing_perms = {p.name: p for p in self.session.query(PermissionModel).all()}
        for perm_name in ALL_PERMISSIONS:
            if perm_name not in existing_perms:
                new_perm = PermissionModel(
                    id=f"perm_{uuid.uuid4().hex[:12]}",
                    name=perm_name,
                    description=f"Permission for {perm_name}",
                )
                self.session.add(new_perm)
                existing_perms[perm_name] = new_perm
        self.session.flush()

        # 2. Create Roles and bind permissions
        existing_roles = {r.name: r for r in self.session.query(RoleModel).all()}
        for role_enum in Role:
            role_name = role_enum.value
            if role_name not in existing_roles:
                new_role = RoleModel(
                    id=f"role_{uuid.uuid4().hex[:12]}",
                    name=role_name,
                    description=f"{role_name} role in Oblivion security model",
                )
                self.session.add(new_role)
                self.session.flush()
                existing_roles[role_name] = new_role

                # Bind permissions
                assigned_perms = ROLE_PERMISSIONS.get(role_name, set())
                for p_name in assigned_perms:
                    perm_obj = existing_perms.get(p_name)
                    if perm_obj:
                        rp = RolePermissionModel(
                            id=f"rp_{uuid.uuid4().hex[:12]}",
                            role_id=new_role.id,
                            permission_id=perm_obj.id,
                        )
                        self.session.add(rp)
        self.session.flush()

    def create_user(
        self,
        username: str,
        password_hash: str | None = None,
        role_names: list[str] | None = None,
        disabled: bool = False,
    ) -> UserModel:
        """Creates a new user and associates assigned roles."""
        # Ensure default roles and permissions exist before binding
        self.init_default_roles_and_permissions()

        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        user = UserModel(
            id=user_id,
            username=username,
            password_hash=password_hash,
            disabled=disabled,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        self.session.add(user)
        self.session.flush()

        if role_names:
            for r_name in role_names:
                role = self.session.query(RoleModel).filter_by(name=r_name.upper()).one_or_none()
                if role:
                    rp = RolePermissionModel(
                        id=f"urp_{uuid.uuid4().hex[:12]}",
                        role_id=role.id,
                        user_id=user.id,
                    )
                    self.session.add(rp)
            self.session.flush()

        return user

    def get_by_username(self, username: str) -> UserModel | None:
        """Look up user by unique username."""
        return self.session.query(UserModel).filter_by(username=username).one_or_none()

    def get_by_id(self, user_id: str) -> UserModel | None:
        """Look up user by ID."""
        return self.session.get(UserModel, user_id)

    def get_user_role_names(self, user_id: str) -> list[str]:
        """Returns the list of role names assigned to a user."""
        rps = self.session.query(RolePermissionModel).filter_by(user_id=user_id).all()
        role_ids = [rp.role_id for rp in rps if rp.role_id]
        if not role_ids:
            return []
        roles = self.session.query(RoleModel).filter(RoleModel.id.in_(role_ids)).all()
        return [r.name for r in roles]

    def create_session(
        self,
        user_id: str,
        token_hash: str,
        expires_at: datetime.datetime,
    ) -> SessionModel:
        """Creates a persistent server-side session."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        sess = SessionModel(
            id=session_id,
            user_id=user_id,
            token_hash=token_hash,
            issued_at=datetime.datetime.now(datetime.UTC),
            expires_at=expires_at,
            revoked=False,
        )
        self.session.add(sess)
        self.session.flush()
        return sess

    def get_session_by_token_hash(self, token_hash: str) -> SessionModel | None:
        """Finds an unrevoked, active session by token SHA-256 hash."""
        now = datetime.datetime.now(datetime.UTC)
        sess = (
            self.session.query(SessionModel)
            .filter(
                SessionModel.token_hash == token_hash,
                SessionModel.revoked == False,
                SessionModel.expires_at > now,
            )
            .one_or_none()
        )
        return sess

    def revoke_session(self, token_hash: str) -> bool:
        """Revokes a session token."""
        sess = self.session.query(SessionModel).filter_by(token_hash=token_hash).one_or_none()
        if sess and not sess.revoked:
            sess.revoked = True
            self.session.flush()
            return True
        return False

    def bootstrap_admin_if_needed(self) -> UserModel | None:
        """
        Safely bootstraps initial ADMIN user if no users exist.
        Uses OBLIVION_BOOTSTRAP_ADMIN_USER and OBLIVION_BOOTSTRAP_ADMIN_PASSWORD.
        Never uses hardcoded admin/admin.
        """
        self.init_default_roles_and_permissions()

        admin_count = self.session.query(UserModel).count()
        if admin_count > 0:
            return None

        bootstrap_user = os.environ.get("OBLIVION_BOOTSTRAP_ADMIN_USER")
        bootstrap_pass = os.environ.get("OBLIVION_BOOTSTRAP_ADMIN_PASSWORD")

        if not bootstrap_user or not bootstrap_pass:
            # Generate random secure credentials if not provided
            import secrets
            bootstrap_user = "admin"
            bootstrap_pass = secrets.token_urlsafe(16)

        hashed = hash_password(bootstrap_pass)
        admin = self.create_user(
            username=bootstrap_user,
            password_hash=hashed,
            role_names=[Role.ADMIN.value],
        )
        return admin
