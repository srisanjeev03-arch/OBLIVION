"""Dry-run contract.

These tests previously asserted ``plan.safety_result["status"] == "APPROVED"``
and ``"None in dry-run" in plan.limitations`` against an implementation that
consulted neither the validator nor the policy engine. Those expectations
described a planning step that approved everything, so they are replaced rather
than adapted. What is asserted now is the contract the brief states: a dry run
observes, never mutates, and never authorizes.
"""

from pathlib import Path

from oblivion.core.dryrun.planner import DryRunPlanner
from oblivion.core.safety.paths import SafePathValidator

SELECTIVE_FILE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"
TREE_POLICY = "ERASURE.LOGICAL.TREE.V1"


def _planner(target, scope, policy_id, validator):
    return DryRunPlanner(
        target=str(target), scope=scope, policy_id=policy_id, validator=validator
    )


# -- it never authorizes ---------------------------------------------------

def test_plan_never_grants_authorization(temp_dir, safe_validator):
    f = temp_dir / "a.txt"
    f.write_text("payload")

    plan = _planner(f, "SELECTIVE_PERMANENT", SELECTIVE_FILE_POLICY, safe_validator).plan()

    assert plan.authorization["granted"] is False
    assert "never authorizes" in plan.authorization["reason"]


def test_plan_reports_no_approved_status_anywhere(temp_dir, safe_validator):
    """The literal approval verdict the old implementation invented is gone."""
    f = temp_dir / "a.txt"
    f.write_text("payload")

    plan = _planner(f, "SELECTIVE_PERMANENT", SELECTIVE_FILE_POLICY, safe_validator).plan()

    assert "status" not in plan.safety_result
    assert "APPROVED" not in str(plan.safety_result)
    assert "APPROVED" not in str(plan.policy_result)


# -- it observes truthfully ------------------------------------------------

def test_plan_uses_the_real_validator_result(temp_dir, safe_validator):
    f = temp_dir / "a.txt"
    f.write_text("payload")

    plan = _planner(f, "SELECTIVE_PERMANENT", SELECTIVE_FILE_POLICY, safe_validator).plan()

    assert plan.safety_result["valid"] is True
    assert plan.policy_result["allowed"] is True
    assert plan.would_proceed is True


def test_plan_reports_refusal_for_a_target_outside_allowed_roots(temp_dir):
    """A target production would refuse must not be reported as proceedable."""
    outside = temp_dir / "outside.txt"
    outside.write_text("payload")
    # Allowed root deliberately excludes the target.
    (temp_dir / "allowed").mkdir()
    validator = SafePathValidator(allowed_roots=[str(temp_dir / "allowed")])

    plan = _planner(outside, "SELECTIVE_PERMANENT", SELECTIVE_FILE_POLICY, validator).plan()

    assert plan.safety_result["valid"] is False
    assert plan.would_proceed is False


def test_plan_surfaces_policy_incompatibility(temp_dir, safe_validator):
    """A file target under a directory-only policy is reported as not allowed."""
    f = temp_dir / "a.txt"
    f.write_text("payload")

    plan = _planner(f, "COMPLETE_ERASURE", TREE_POLICY, safe_validator).plan()

    assert plan.policy_result["allowed"] is False
    assert plan.would_proceed is False


def test_plan_enumerates_real_files_and_sizes(temp_dir, safe_validator):
    (temp_dir / "one.txt").write_text("aaa")
    (temp_dir / "two.txt").write_text("bbbb")

    plan = _planner(temp_dir, "COMPLETE_ERASURE", TREE_POLICY, safe_validator).plan()

    assert len(plan.files) == 2
    assert plan.total_size_bytes == 7
    assert Path(plan.files[0]).exists()


def test_missing_target_is_reported_not_assumed(temp_dir, safe_validator):
    plan = _planner(
        temp_dir / "nope.txt", "SELECTIVE_PERMANENT", SELECTIVE_FILE_POLICY, safe_validator
    ).plan()

    assert plan.would_proceed is False
    assert plan.policy_result["evaluated"] is False
    assert any("does not currently exist" in w for w in plan.warnings)


def test_plan_states_its_limitations(temp_dir, safe_validator):
    f = temp_dir / "a.txt"
    f.write_text("payload")

    plan = _planner(f, "SELECTIVE_PERMANENT", SELECTIVE_FILE_POLICY, safe_validator).plan()

    joined = " ".join(plan.limitations).lower()
    assert "logical deletion only" in joined
    assert "confers no authorization" in joined
    assert "None in dry-run" not in plan.limitations


# -- it mutates nothing ----------------------------------------------------

def test_plan_does_not_mutate_the_target(temp_dir, safe_validator):
    (temp_dir / "one.txt").write_text("aaa")
    (temp_dir / "two.txt").write_text("bbbb")

    planner = _planner(temp_dir, "COMPLETE_ERASURE", TREE_POLICY, safe_validator)
    planner.capture_pre_state()
    plan = planner.plan()

    assert planner.verify_post_state() is True
    assert plan.mutations == []
    assert (temp_dir / "one.txt").read_text() == "aaa"
    assert (temp_dir / "two.txt").read_text() == "bbbb"


def test_verify_post_state_is_false_without_a_capture(temp_dir, safe_validator):
    """An unverified "nothing changed" claim must not be made."""
    planner = _planner(temp_dir, "COMPLETE_ERASURE", TREE_POLICY, safe_validator)
    assert planner.verify_post_state() is False


def test_verify_post_state_detects_a_real_change(temp_dir, safe_validator):
    f = temp_dir / "one.txt"
    f.write_text("aaa")

    planner = _planner(temp_dir, "COMPLETE_ERASURE", TREE_POLICY, safe_validator)
    planner.capture_pre_state()
    f.write_text("changed")

    assert planner.verify_post_state() is False
