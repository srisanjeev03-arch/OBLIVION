"""Five-Role Security Model and Fine-Grained Permissions."""
from collections.abc import Collection
from enum import Enum


class Role(str, Enum):
    """The five authorized roles in Oblivion."""
    ADMIN = "ADMIN"
    INVESTIGATOR = "INVESTIGATOR"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"
    VIEWER = "VIEWER"


class Permission(str, Enum):
    """Fine-grained permission identifiers."""
    # Case management
    CASE_CREATE = "case.create"
    CASE_VIEW = "case.view"
    CASE_UPDATE = "case.update"
    CASE_CLOSE = "case.close"

    # Evidence handling
    EVIDENCE_IMPORT = "evidence.import"
    EVIDENCE_VIEW = "evidence.view"
    EVIDENCE_HASH = "evidence.hash"
    EVIDENCE_VERIFY = "evidence.verify"

    # Erasure & Sanitization requests/execution
    FILE_ERASURE_REQUEST = "file_erasure.request"
    FILE_ERASURE_EXECUTE = "file_erasure.execute"
    DRIVE_SANITIZATION_REQUEST = "drive_sanitization.request"
    DRIVE_SANITIZATION_EXECUTE = "drive_sanitization.execute"

    # Recovery
    RECOVERY_VIEW = "recovery.view"
    RECOVERY_EXECUTE = "recovery.execute"

    # Operations & Workflow
    OPERATION_VIEW = "operation.view"
    OPERATION_REQUEST = "operation.request"
    OPERATION_APPROVE = "operation.approve"
    OPERATION_EXECUTE = "operation.execute"
    OPERATION_VERIFY = "operation.verify"

    # Audit & Inspection
    AUDIT_VIEW = "audit.view"
    AUDIT_VERIFY = "audit.verify"

    # Reporting
    REPORT_EXPORT = "report.export"

    # Administration
    USER_MANAGE = "user.manage"
    ROLE_MANAGE = "role.manage"
    PERMISSION_MANAGE = "permission.manage"
    SYSTEM_CONFIGURE = "system.configure"


ALL_PERMISSIONS: set[str] = {p.value for p in Permission}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: ALL_PERMISSIONS,

    Role.INVESTIGATOR.value: {
        Permission.CASE_CREATE.value,
        Permission.CASE_VIEW.value,
        Permission.CASE_UPDATE.value,
        Permission.CASE_CLOSE.value,
        Permission.EVIDENCE_IMPORT.value,
        Permission.EVIDENCE_VIEW.value,
        Permission.EVIDENCE_HASH.value,
        Permission.FILE_ERASURE_REQUEST.value,
        Permission.DRIVE_SANITIZATION_REQUEST.value,
        Permission.RECOVERY_VIEW.value,
        Permission.RECOVERY_EXECUTE.value,
        Permission.OPERATION_VIEW.value,
        Permission.OPERATION_REQUEST.value,
        Permission.REPORT_EXPORT.value,
    },

    Role.OPERATOR.value: {
        Permission.CASE_VIEW.value,
        Permission.EVIDENCE_VIEW.value,
        Permission.EVIDENCE_HASH.value,
        Permission.FILE_ERASURE_EXECUTE.value,
        Permission.DRIVE_SANITIZATION_EXECUTE.value,
        Permission.RECOVERY_VIEW.value,
        Permission.OPERATION_VIEW.value,
        Permission.OPERATION_EXECUTE.value,
        Permission.REPORT_EXPORT.value,
    },

    Role.AUDITOR.value: {
        Permission.CASE_VIEW.value,
        Permission.EVIDENCE_VIEW.value,
        Permission.EVIDENCE_VERIFY.value,
        Permission.RECOVERY_VIEW.value,
        Permission.OPERATION_VIEW.value,
        Permission.OPERATION_VERIFY.value,
        Permission.AUDIT_VIEW.value,
        Permission.AUDIT_VERIFY.value,
        Permission.REPORT_EXPORT.value,
    },

    Role.VIEWER.value: {
        Permission.CASE_VIEW.value,
        Permission.EVIDENCE_VIEW.value,
        Permission.OPERATION_VIEW.value,
        Permission.REPORT_EXPORT.value,
    },
}


def get_role_permissions(roles: Collection[str]) -> set[str]:
    """Resolves all permissions granted to a collection of role names."""
    permissions: set[str] = set()
    for r in roles:
        role_upper = r.upper()
        if role_upper in ROLE_PERMISSIONS:
            permissions.update(ROLE_PERMISSIONS[role_upper])
    return permissions


def has_permission(roles: Collection[str], required_permission: str) -> bool:
    """Evaluates whether the provided roles grant the required permission."""
    granted = get_role_permissions(roles)
    return required_permission in granted
