import json
from scripts.core.services.agent_game_review_service import merge_game_review_payload
from scripts.schemas.agent import AgentValidationSummary


def test_source_change_review_is_job_scoped_and_not_model_repairable(tmp_path):
    root = tmp_path / "current"
    root.mkdir()
    (root / "UI.json").write_text('{}', encoding="utf-8")
    (root / ".remis-localization-manifest.json").write_text(json.dumps({
        "game_id": "project_zomboid", "files": {"UI.json": {"entries": [
            {"key": "UI::changed", "needs_review": True}, {"key": "UI::same", "needs_review": False}]}}}), encoding="utf-8")
    payload = {"summary": AgentValidationSummary(), "items": [], "_raw_items": []}
    actual = merge_game_review_payload(payload, "project_zomboid", [str(root)], tmp_path)
    assert actual["summary"].human_review_items == 1
    assert actual["items"][0]["code"] == "source_changed_review_required"
    from scripts.core.services.agent_validation_policy import repairable_issues
    assert not repairable_issues(actual["_raw_items"])
    assert merge_game_review_payload(payload, "rimworld", [str(root)], tmp_path) == payload
    assert merge_game_review_payload(payload, "project_zomboid", [], tmp_path) == payload
    assert merge_game_review_payload(payload, "project_zomboid", [str(root)], tmp_path / "other") == payload
    assert merge_game_review_payload(actual, "project_zomboid", [str(root)], tmp_path)["summary"].total == 1
