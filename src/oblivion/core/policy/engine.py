"""Policy validation engine and allowlist registry."""
from dataclasses import dataclass


class PolicyError(Exception):
    """Raised when a requested policy is invalid, not allowlisted, or incompatible."""


@dataclass(frozen=True)
class PolicyDefinition:
    policy_id: str
    name: str
    allowed_modes: set[str]
    allowed_target_types: set[str]  # {"file"}, {"directory"}, {"file", "directory"}
    requires_approval: bool
    description: str


# Canonical allowlisted policies per reference/POLICY_IDS.md and specs
POLICY_REGISTRY: dict[str, PolicyDefinition] = {
    "ERASURE.LOGICAL.SELECTIVE.V1": PolicyDefinition(
        policy_id="ERASURE.LOGICAL.SELECTIVE.V1",
        name="Logical Selective File Erasure v1",
        allowed_modes={"SELECTIVE_PERMANENT"},
        allowed_target_types={"file"},
        requires_approval=True,
        description="Permanently unlinks selected files under supported logical-erasure scope.",
    ),
    "ERASURE.LOGICAL.TREE.V1": PolicyDefinition(
        policy_id="ERASURE.LOGICAL.TREE.V1",
        name="Logical Tree Erasure v1",
        allowed_modes={"COMPLETE_ERASURE"},
        allowed_target_types={"directory"},
        requires_approval=True,
        description="Permanently removes all validated contents under a folder/tree target.",
    ),
    "ERASURE.RECOVERABLE.ENCRYPTED.V1": PolicyDefinition(
        policy_id="ERASURE.RECOVERABLE.ENCRYPTED.V1",
        name="Controlled Recoverable Encrypted Erasure v1",
        allowed_modes={"CONTROLLED_RECOVERABLE"},
        allowed_target_types={"file"},
        requires_approval=True,
        description="Preserves an authenticated AES-256-GCM recovery object in vault before unlinking.",
    ),
}


class PolicyEngine:
    """Evaluates and enforces allowlisted policies server-side."""

    @staticmethod
    def get_policy(policy_id: str) -> PolicyDefinition | None:
        """Resolves a policy definition from the allowlisted registry."""
        return POLICY_REGISTRY.get(policy_id)

    @staticmethod
    def list_policies() -> list[PolicyDefinition]:
        """Returns all allowlisted policies."""
        return list(POLICY_REGISTRY.values())

    @classmethod
    def validate_operation_policy(
        cls,
        policy_id: str,
        mode: str,
        target_type: str,
    ) -> PolicyDefinition:
        """
        Validates that policy_id is allowlisted and fully compatible with the requested mode and target type.
        Raises PolicyError if validation fails (fail-closed).
        """
        if not policy_id:
            raise PolicyError("Policy ID must be specified")

        policy = cls.get_policy(policy_id)
        if not policy:
            raise PolicyError(f"Policy '{policy_id}' is not allowlisted")

        if mode not in policy.allowed_modes:
            raise PolicyError(
                f"Policy '{policy_id}' does not support mode '{mode}'. Allowed modes: {list(policy.allowed_modes)}"
            )

        if target_type not in policy.allowed_target_types:
            raise PolicyError(
                f"Policy '{policy_id}' is incompatible with target type '{target_type}'. Allowed types: {list(policy.allowed_target_types)}"
            )

        return policy
