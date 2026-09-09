from oblivion.core.dryrun.planner import DryRunPlanner


def test_dryrun_plan():
    planner = DryRunPlanner(target="C:\\test", scope="COMPLETE_ERASURE", policy_id="P1")
    plan = planner.plan()

    assert plan.target == "C:\\test"
    assert plan.safety_result["status"] == "APPROVED"
    assert "None in dry-run" in plan.limitations

def test_dryrun_state_verification():
    planner = DryRunPlanner(target="C:\\test", scope="COMPLETE_ERASURE", policy_id="P1")
    planner.capture_pre_state()
    assert planner.verify_post_state() is True
