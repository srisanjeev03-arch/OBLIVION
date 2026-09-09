"""Separation of Duties (SoD) engine."""


class SoDViolationError(Exception):
    """Raised when an operation violates Separation of Duties constraints."""


def validate_approval(requested_by: str | None, approving_actor_id: str) -> None:
    """
    Enforces that the requester of a sensitive operation cannot approve their own request.
    """
    if not approving_actor_id:
        raise SoDViolationError("Approving actor ID must be non-empty")

    if requested_by and requested_by == approving_actor_id:
        raise SoDViolationError(
            f"Separation of Duties violation: Requester '{requested_by}' cannot approve their own operation."
        )


def validate_verification(executed_by: str | None, verifying_actor_id: str) -> None:
    """
    Enforces that the executor of an operation cannot verify their own execution result.
    """
    if not verifying_actor_id:
        raise SoDViolationError("Verifying actor ID must be non-empty")

    if executed_by and executed_by == verifying_actor_id:
        raise SoDViolationError(
            f"Separation of Duties violation: Executor '{executed_by}' cannot verify their own operation."
        )
