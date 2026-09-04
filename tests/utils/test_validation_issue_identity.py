import pytest
from fastapi import HTTPException

from scripts.core.services.validation_sidecar_service import ValidationSidecarService
from scripts.core.services.workshop_issue_binding_service import bind_repair_issues
from scripts.utils.validation_issue_identity import enrich_issue, reconcile_issues
from scripts.utils.validation_logger import ValidationLogger


def _issue(target="旧译文", **extra):
    return {
        "project_id": "project-1",
        "target_lang": "zh-CN",
        "file_name": "localization/english/demo_l_english.yml",
        "source_file": "localization/english/demo_l_english.yml",
        "key": "demo.one:0",
        "line_number": 4,
        "source_str": "Source $VALUE$",
        "target_str": target,
        "error_type": "validation_error",
        "error_code": "validation_error",
        "details": "broken",
        "status": "detected",
        **extra,
    }


def test_issue_identity_does_not_change_when_only_target_changes():
    old = enrich_issue(_issue("旧译文"))
    new = enrich_issue(_issue("新译文"))

    assert old["issue_id"] == new["issue_id"]
    assert old["observation_fingerprint"] != new["observation_fingerprint"]


def test_reconcile_preserves_assessment_until_target_changes():
    old = enrich_issue(_issue("旧译文"))
    old.update({
        "status": "review",
        "disposition": "human_review",
        "assessment": {"verdict": "uncertain"},
        "attempts": 2,
    })

    same = reconcile_issues([_issue("旧译文")], [old])[0]
    changed = reconcile_issues([_issue("新译文")], [old])[0]

    assert same["status"] == "review"
    assert same["assessment"] == {"verdict": "uncertain"}
    assert same["attempts"] == 2
    assert changed["status"] == "detected"
    assert "assessment" not in changed


def test_sidecar_separates_repair_and_review_queues():
    service = ValidationSidecarService()
    items = service.active_issues([
        _issue(error_code="validation_format_structure_mismatch"),
        _issue(
            key="demo.two:0",
            error_code="validation_source_format_unbalanced",
            details_params={
                "classification": "source_defect",
                "repairQueue": False,
                "reviewQueue": True,
            },
        ),
    ])

    assert len(service.repair_issues(items)) == 1
    assert len(service.review_issues(items)) == 1


def test_attempt_status_updates_only_the_stable_issue(tmp_path):
    first = enrich_issue(_issue("旧译文"))
    second = enrich_issue(_issue("另一条", key="demo.two:0"))
    ValidationLogger.save_errors(str(tmp_path), [first, second])

    ValidationLogger.mark_attempt_result(
        str(tmp_path),
        first["file_name"],
        first["key"],
        issue_id=first["issue_id"],
        status="fixed",
        last_suggested_fix="修复",
    )

    errors = ValidationLogger.load_errors(str(tmp_path))
    assert errors[0]["status"] == "fixed"
    assert errors[0]["attempts"] == 1
    assert errors[1]["status"] == "detected"


def test_issue_id_does_not_fallback_to_ambiguous_legacy_file_key(tmp_path):
    first = _issue("旧译文")
    second = _issue("另一条")
    second["key"] = first["key"]
    second_id = enrich_issue(second, occurrence=1)["issue_id"]
    ValidationLogger.save_errors(str(tmp_path), [first, second])

    ValidationLogger.mark_attempt_result(
        str(tmp_path),
        first["file_name"],
        first["key"],
        issue_id=second_id,
        status="fixed",
    )

    errors = ValidationLogger.load_errors(str(tmp_path))
    assert [error.get("status", "detected") for error in errors] == ["detected", "detected"]


def test_repair_binding_rejects_stale_target_snapshot(tmp_path):
    current = enrich_issue(_issue("当前译文"))

    class Sidecars:
        def current_translation_issues(self, _project_root):
            return [current]

    submitted = {
        **current,
        "target_str": "过期译文",
    }
    with pytest.raises(HTTPException) as exc_info:
        bind_repair_issues(
            {"project_id": "project-1", "source_path": str(tmp_path)},
            [submitted],
            sidecars=Sidecars(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "stale_validation_issue"
