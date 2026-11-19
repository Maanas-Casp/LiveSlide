from liveslide_agents.workflow import risk_workflow


def test_below_warn_threshold_does_not_create_draft():
    assert risk_workflow.invoke({"risk_p": 0.799})["decision"] == "close_without_alert"


def test_warn_threshold_pauses_at_officer_approval():
    assert risk_workflow.invoke({"risk_p": 0.8})["decision"] == "waiting_for_approval"
