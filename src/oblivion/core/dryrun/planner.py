"""Dry-run planning.

A dry run answers "what would this operation touch, and would it be allowed?"
It is observational: it reads the filesystem and runs the same validation the
real operation would, and it changes nothing.

It deliberately does **not** authorize anything. An earlier revision returned a
hardcoded ``safety_result={"status": "APPROVED"}`` without consulting the
validator or the policy engine at all, which meant a planning step - the very
step an operator uses to decide whether an operation is safe - reported approval
for targets that production would refuse. The word "APPROVED" is gone: this
module reports what the validator and the policy engine actually said, and
states plainly that authorization is a separate, human, step.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oblivion.core.policy import PolicyEngine, PolicyError
from oblivion.core.safety.paths import PathSafetyError, SafePathValidator

#: Limitations that are true of every dry run, regardless of target.
INHERENT_LIMITATIONS = (
    "A plan describes the target as observed now; the filesystem may change "
    "before execution, which is why execution revalidates target identity.",
    "Erasure in this build is logical deletion only. A plan cannot predict "
    "physical media state.",
    "A dry run confers no authorization. Execution requires approval by a "
    "separate actor under separation of duties.",
)


@dataclass
class DryRunPlan:
    """What a dry run observed. Every field is measured or quoted, never assumed."""

    target: str
    canonical_target: str | None
    scope: str
    policy_id: str
    files: list[str]
    total_size_bytes: int
    filesystem: str
    storage_profile: dict[str, Any]
    #: Verbatim output of ``SafePathValidator.validate_target``.
    safety_result: dict[str, Any]
    #: Outcome of the server-side policy allowlist check.
    policy_result: dict[str, Any]
    #: Always ``granted: False``. A plan is not a decision.
    authorization: dict[str, Any]
    #: True only when safety and policy both passed. Still not an authorization.
    would_proceed: bool
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    #: Changes this dry run made. Always empty; asserted by the tests.
    mutations: list[str] = field(default_factory=list)


class DryRunPlanner:
    """Plans an operation without executing or authorizing it."""

    def __init__(
        self,
        target: str,
        scope: str,
        policy_id: str,
        validator: SafePathValidator | None = None,
    ):
        self.target = target
        self.scope = scope
        self.policy_id = policy_id
        self.validator = validator or SafePathValidator()
        self._pre_state_snapshot: dict[str, tuple[int, int]] | None = None

    # -- observational state capture ---------------------------------------

    def _inventory(self) -> dict[str, tuple[int, int]]:
        """Read-only inventory of the target subtree: path -> (size, mtime_ns).

        Uses ``os.walk`` without following links, and ``os.stat`` only. Nothing
        is opened for writing and nothing is removed.
        """
        inventory: dict[str, tuple[int, int]] = {}
        p = Path(self.target)
        if not p.exists():
            return inventory
        if p.is_file():
            st = p.stat()
            inventory[str(p)] = (st.st_size, st.st_mtime_ns)
            return inventory
        for root, _dirs, files in os.walk(str(p), followlinks=False):
            for name in files:
                fp = Path(root) / name
                try:
                    st = fp.stat()
                    inventory[str(fp)] = (st.st_size, st.st_mtime_ns)
                except OSError:
                    # Unreadable entries are recorded as present but unmeasured
                    # rather than silently dropped from the plan.
                    inventory[str(fp)] = (-1, -1)
        return inventory

    def capture_pre_state(self) -> None:
        """Record the target's observable state before planning."""
        self._pre_state_snapshot = self._inventory()

    def verify_post_state(self) -> bool:
        """True when the target is byte-for-byte unchanged since capture.

        Returns ``False`` when no snapshot was taken - an unverified claim of
        "nothing changed" is exactly the kind of assertion this module exists to
        avoid making.
        """
        if self._pre_state_snapshot is None:
            return False
        return self._inventory() == self._pre_state_snapshot

    # -- planning ----------------------------------------------------------

    def _target_type(self) -> str | None:
        p = Path(self.target)
        if p.is_dir():
            return "directory"
        if p.is_file():
            return "file"
        return None

    def _evaluate_policy(self, target_type: str | None) -> dict[str, Any]:
        if target_type is None:
            return {
                "evaluated": False,
                "allowed": False,
                "reason": "Target does not exist, so its type cannot be determined.",
            }
        try:
            definition = PolicyEngine.validate_operation_policy(
                policy_id=self.policy_id,
                mode=self.scope,
                target_type=target_type,
            )
        except PolicyError as exc:
            return {"evaluated": True, "allowed": False, "reason": str(exc)}
        return {
            "evaluated": True,
            "allowed": True,
            "policy_id": definition.policy_id,
            "requires_approval": definition.requires_approval,
        }

    def plan(self) -> DryRunPlan:
        """Produce the plan. Performs no mutation and grants no authorization."""
        warnings: list[str] = []
        limitations = list(INHERENT_LIMITATIONS)

        try:
            canonical = self.validator.canonicalize(self.target)
        except PathSafetyError as exc:
            canonical = None
            warnings.append(f"Target could not be canonicalized: {exc}")

        is_tree = self._target_type() == "directory"
        if canonical is None:
            safety_result: dict[str, Any] = {
                "valid": False,
                "errors": ["Target could not be canonicalized"],
                "warnings": [],
            }
        else:
            safety_result = self.validator.validate_target(
                canonical, is_directory_tree=is_tree
            )

        target_type = self._target_type()
        if target_type is None:
            warnings.append("Target does not currently exist.")

        policy_result = self._evaluate_policy(target_type)

        inventory = self._inventory()
        files = sorted(inventory)
        total_size = sum(size for size, _ in inventory.values() if size >= 0)
        if any(size < 0 for size, _ in inventory.values()):
            warnings.append(
                "Some entries could not be measured; reported size is a lower bound."
            )

        # Storage profile is read-only and best-effort. It reports UNKNOWN rather
        # than guessing when the platform cannot answer.
        storage_profile: dict[str, Any] = {}
        filesystem = "UNKNOWN"
        try:
            from oblivion.core.discovery import StorageProfiler

            storage_profile = StorageProfiler().profile(self.target)
            filesystem = str(storage_profile.get("filesystem", "UNKNOWN"))
        except Exception as exc:  # pragma: no cover - platform dependent
            warnings.append(f"Storage profile unavailable: {type(exc).__name__}")

        would_proceed = bool(safety_result.get("valid")) and bool(
            policy_result.get("allowed")
        )
        if not would_proceed:
            limitations.append(
                "This target would be refused as planned; see safety_result and "
                "policy_result."
            )

        return DryRunPlan(
            target=self.target,
            canonical_target=canonical,
            scope=self.scope,
            policy_id=self.policy_id,
            files=files,
            total_size_bytes=total_size,
            filesystem=filesystem,
            storage_profile=storage_profile,
            safety_result=safety_result,
            policy_result=policy_result,
            authorization={
                "granted": False,
                "reason": (
                    "A dry run never authorizes an operation. Execution requires "
                    "an approval recorded against the operation by a different "
                    "actor than the requester."
                ),
            },
            would_proceed=would_proceed,
            warnings=warnings,
            limitations=limitations,
            mutations=[],
        )
