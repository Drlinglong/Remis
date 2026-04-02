import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from scripts.core.project_json_manager import ProjectJsonManager
from scripts.routers.agent_workshop import apply_translation_fix_to_file
from scripts.utils.validation_logger import ValidationLogger
from scripts.web_server import app


client = TestClient(app)


def _write_loc_file(path: Path, header: str, entries: list[tuple[str, str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{header}:\n"]
    for key, value in entries:
        lines.append(f' {key} "{value}"\n')
    path.write_text("".join(lines), encoding="utf-8-sig")


def test_load_cached_filters_fixed_entries(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    ValidationLogger.save_errors(str(project_root), [
        {
            "file_name": "a.yml",
            "key": "demo.one",
            "source_str": "src",
            "target_str": "dst",
            "error_type": "validation_error",
            "details": "broken",
            "status": "detected",
        },
        {
            "file_name": "b.yml",
            "key": "demo.two",
            "source_str": "src",
            "target_str": "dst",
            "error_type": "validation_error",
            "details": "broken",
            "status": "fixed",
        },
    ])

    with patch("scripts.routers.agent_workshop.project_manager", new_callable=MagicMock) as mock_pm:
        mock_pm.get_project = AsyncMock(return_value={
            "project_id": "p1",
            "source_path": str(project_root),
            "game_id": "victoria3",
        })

        response = client.get("/api/agent-workshop/load-cached", params={"project_id": "p1"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["file_name"] == "a.yml"
    assert data[0]["status"] == "detected"


def test_load_cached_falls_back_to_workshop_sidecar(tmp_path):
    project_root = tmp_path / "project"
    translation_root = tmp_path / "translation"
    project_root.mkdir()
    translation_root.mkdir()

    ProjectJsonManager(str(project_root)).update_config({
        "translation_dirs": [str(translation_root)]
    })
    (translation_root / "workshop_issues.json").write_text(
        json.dumps({
            "generated_at": "2026-04-03T10:00:00",
            "issue_count": 2,
            "issues": [
                {
                    "file_name": "events/test_l_simp_chinese.yml",
                    "key": "demo.one",
                    "source_str": "Hello",
                    "target_str": "坏译文",
                    "error_type": "validation_error",
                    "error_code": "validation_error",
                    "details": "broken",
                    "status": "detected",
                },
                {
                    "file_name": "events/test_l_simp_chinese.yml",
                    "key": "demo.two",
                    "source_str": "World",
                    "target_str": "旧译文",
                    "error_type": "validation_error",
                    "error_code": "validation_error",
                    "details": "broken",
                    "status": "fixed",
                },
            ],
        }),
        encoding="utf-8",
    )

    with patch("scripts.routers.agent_workshop.project_manager", new_callable=MagicMock) as mock_pm:
        mock_pm.get_project = AsyncMock(return_value={
            "project_id": "p2",
            "source_path": str(project_root),
            "game_id": "victoria3",
        })

        response = client.get("/api/agent-workshop/load-cached", params={"project_id": "p2"})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["key"] == "demo.one"

    cached = ValidationLogger.load_errors(str(project_root))
    assert len(cached) == 1
    assert cached[0]["key"] == "demo.one"


def test_fix_issue_updates_file_status_and_report(tmp_path):
    project_root = tmp_path / "project"
    translation_root = tmp_path / "translation"
    translation_file = translation_root / "events" / "test_l_simp_chinese.yml"
    project_root.mkdir()
    ProjectJsonManager(str(project_root)).update_config({
        "translation_dirs": [str(translation_root)]
    })
    _write_loc_file(
        translation_file,
        "l_simp_chinese",
        [("demo.one:0", "坏译文"), ("demo.two:0", "其他内容")],
    )
    ValidationLogger.save_errors(str(project_root), [{
        "file_name": "events/test_l_simp_chinese.yml",
        "key": "demo.one:0",
        "source_str": "Hello",
        "target_str": "坏译文",
        "error_type": "validation_error",
        "details": "broken",
        "status": "detected",
    }])

    mock_agent = MagicMock()
    mock_agent.fix_issue_loop = AsyncMock(return_value={
        "suggested_fix": "修复译文",
        "reflection": "placeholder",
        "status": "SUCCESS",
        "parity_message": "Validation passed",
    })

    with patch("scripts.routers.agent_workshop.project_manager", new_callable=MagicMock) as mock_pm, \
         patch("scripts.routers.agent_workshop.ReflexionFixAgent", return_value=mock_agent), \
         patch("scripts.core.api_handler.get_handler", return_value=MagicMock()):
        mock_pm.get_project = AsyncMock(return_value={
            "project_id": "p3",
            "source_path": str(project_root),
            "game_id": "victoria3",
        })

        response = client.post("/api/agent-workshop/fix", json={
            "project_id": "p3",
            "file_name": "events/test_l_simp_chinese.yml",
            "file_path": str(translation_file),
            "key": "demo.one:0",
            "source_str": "Hello",
            "target_str": "坏译文",
            "error_type": "validation_error",
            "details": "broken",
            "api_provider": "gemini",
            "api_model": "gemini-3-flash-preview",
        })

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["suggested_fix"] == "修复译文"
    assert payload["report_path"]
    assert Path(payload["report_path"]).exists()

    content = translation_file.read_text(encoding="utf-8-sig")
    assert 'demo.one:0 "修复译文"' in content

    cached = ValidationLogger.load_errors(str(project_root))
    assert cached[0]["status"] == "fixed"


def test_fix_issue_does_not_mark_fixed_when_apply_fails(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    ValidationLogger.save_errors(str(project_root), [{
        "file_name": "events/test_l_simp_chinese.yml",
        "key": "demo.one:0",
        "source_str": "Hello",
        "target_str": "坏译文",
        "error_type": "validation_error",
        "details": "broken",
        "status": "detected",
    }])

    mock_agent = MagicMock()
    mock_agent.fix_issue_loop = AsyncMock(return_value={
        "suggested_fix": "修复译文",
        "reflection": "placeholder",
        "status": "SUCCESS",
        "parity_message": "Validation passed",
    })

    with patch("scripts.routers.agent_workshop.project_manager", new_callable=MagicMock) as mock_pm, \
         patch("scripts.routers.agent_workshop.ReflexionFixAgent", return_value=mock_agent), \
         patch("scripts.core.api_handler.get_handler", return_value=MagicMock()):
        mock_pm.get_project = AsyncMock(return_value={
            "project_id": "p5",
            "source_path": str(project_root),
            "game_id": "victoria3",
        })

        response = client.post("/api/agent-workshop/fix", json={
            "project_id": "p5",
            "file_name": "events/test_l_simp_chinese.yml",
            "key": "demo.one:0",
            "source_str": "Hello",
            "target_str": "坏译文",
            "error_type": "validation_error",
            "details": "broken",
            "api_provider": "gemini",
            "api_model": "gemini-3-flash-preview",
        })

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "FAILED"
    assert "Target file not found" in payload["parity_message"]
    assert payload["report_path"] is None

    cached = ValidationLogger.load_errors(str(project_root))
    assert cached[0]["status"] == "failed"
    assert cached[0]["failure_reason"] == "target_not_found"
    assert "Target file not found" in cached[0]["failure_details"]
    assert cached[0]["last_suggested_fix"] == payload["suggested_fix"]
    assert cached[0]["last_attempt_at"]


def test_fix_batch_only_marks_successful_items_fixed(tmp_path):
    project_root = tmp_path / "project"
    translation_root = tmp_path / "translation"
    translation_file = translation_root / "events" / "test_l_simp_chinese.yml"
    project_root.mkdir()
    ProjectJsonManager(str(project_root)).update_config({
        "translation_dirs": [str(translation_root)]
    })
    _write_loc_file(
        translation_file,
        "l_simp_chinese",
        [("demo.one:0", "坏译文一"), ("demo.two:0", "坏译文二")],
    )
    ValidationLogger.save_errors(str(project_root), [
        {
            "file_name": "events/test_l_simp_chinese.yml",
            "key": "demo.one:0",
            "source_str": "Hello",
            "target_str": "坏译文一",
            "error_type": "validation_error",
            "details": "broken",
            "status": "detected",
        },
        {
            "file_name": "events/test_l_simp_chinese.yml",
            "key": "demo.two:0",
            "source_str": "World",
            "target_str": "坏译文二",
            "error_type": "validation_error",
            "details": "broken",
            "status": "detected",
        },
    ])

    mock_agent = MagicMock()
    mock_agent.fix_batch_loop = AsyncMock(return_value={
        "results": [
            {
                "file_name": "events/test_l_simp_chinese.yml",
                "key": "demo.one:0",
                "suggested_fix": "修复一",
                "status": "SUCCESS",
                "parity_message": "Validation passed",
            },
            {
                "file_name": "events/test_l_simp_chinese.yml",
                "key": "demo.two:0",
                "suggested_fix": "失败建议",
                "status": "FAILED",
                "parity_message": "Still broken",
            },
        ]
    })

    with patch("scripts.routers.agent_workshop.project_manager", new_callable=MagicMock) as mock_pm, \
         patch("scripts.routers.agent_workshop.ReflexionFixAgent", return_value=mock_agent), \
         patch("scripts.core.api_handler.get_handler", return_value=MagicMock()):
        mock_pm.get_project = AsyncMock(return_value={
            "project_id": "p4",
            "source_path": str(project_root),
            "game_id": "victoria3",
        })

        response = client.post("/api/agent-workshop/fix-batch", json={
            "project_id": "p4",
            "api_provider": "gemini",
            "api_model": "gemini-3-flash-preview",
            "issues": [
                {
                    "file_name": "events/test_l_simp_chinese.yml",
                    "file_path": str(translation_file),
                    "key": "demo.one:0",
                    "source_str": "Hello",
                    "target_str": "坏译文一",
                    "error_type": "validation_error",
                    "details": "broken",
                },
                {
                    "file_name": "events/test_l_simp_chinese.yml",
                    "file_path": str(translation_file),
                    "key": "demo.two:0",
                    "source_str": "World",
                    "target_str": "坏译文二",
                    "error_type": "validation_error",
                    "details": "broken",
                },
            ],
        })

    assert response.status_code == 200
    results = response.json()["results"]
    assert [item["status"] for item in results] == ["SUCCESS", "FAILED"]
    assert results[0]["report_path"]
    assert results[1]["report_path"] is None

    content = translation_file.read_text(encoding="utf-8-sig")
    assert 'demo.one:0 "修复一"' in content
    assert 'demo.two:0 "坏译文二"' in content

    status_map = {
        item["key"]: item["status"]
        for item in ValidationLogger.load_errors(str(project_root))
    }
    assert status_map["demo.one:0"] == "fixed"
    assert status_map["demo.two:0"] == "detected"


def test_fix_batch_does_not_mark_fixed_when_post_validation_fails(tmp_path):
    project_root = tmp_path / "project"
    translation_root = tmp_path / "translation"
    translation_file = translation_root / "events" / "test_l_simp_chinese.yml"
    project_root.mkdir()
    ProjectJsonManager(str(project_root)).update_config({
        "translation_dirs": [str(translation_root)]
    })
    _write_loc_file(
        translation_file,
        "l_simp_chinese",
        [("demo.one:0", "坏译文一")],
    )
    ValidationLogger.save_errors(str(project_root), [{
        "file_name": "events/test_l_simp_chinese.yml",
        "key": "demo.one:0",
        "source_str": "Hello",
        "target_str": "坏译文一",
        "error_type": "validation_error",
        "details": "broken",
        "status": "detected",
        "target_lang": "zh-CN",
    }])

    mock_agent = MagicMock()
    mock_agent.fix_batch_loop = AsyncMock(return_value={
        "results": [
            {
                "file_name": "events/test_l_simp_chinese.yml",
                "key": "demo.one:0",
                "suggested_fix": "会写回但校验失败",
                "status": "SUCCESS",
                "parity_message": "Validation passed",
            }
        ]
    })

    fake_error = MagicMock()
    fake_error.level.value = "error"
    fake_error.message = "still_invalid"

    with patch("scripts.routers.agent_workshop.project_manager", new_callable=MagicMock) as mock_pm, \
         patch("scripts.routers.agent_workshop.ReflexionFixAgent", return_value=mock_agent), \
         patch("scripts.core.api_handler.get_handler", return_value=MagicMock()), \
         patch("scripts.routers.agent_workshop.PostProcessValidator") as mock_validator_cls:
        mock_pm.get_project = AsyncMock(return_value={
            "project_id": "p6",
            "source_path": str(project_root),
            "game_id": "victoria3",
        })
        mock_validator_cls.return_value.validate_entry.return_value = [fake_error]

        response = client.post("/api/agent-workshop/fix-batch", json={
            "project_id": "p6",
            "api_provider": "gemini",
            "api_model": "gemini-3-flash-preview",
            "issues": [
                {
                    "file_name": "events/test_l_simp_chinese.yml",
                    "file_path": str(translation_file),
                    "key": "demo.one:0",
                    "source_str": "Hello",
                    "target_str": "坏译文一",
                    "error_type": "validation_error",
                    "details": "broken",
                    "target_lang": "zh-CN",
                }
            ],
        })

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "FAILED"
    assert "Post-write validation failed" in result["parity_message"]
    assert result["report_path"] is None

    cached = ValidationLogger.load_errors(str(project_root))
    assert cached[0]["status"] == "failed"
    assert cached[0]["failure_reason"] == "post_validation_failure"
    assert "Post-write validation failed" in cached[0]["failure_details"]
    assert cached[0]["last_suggested_fix"] == result["suggested_fix"]
    assert cached[0]["last_attempt_at"]


def test_apply_translation_fix_to_file_escapes_quotes(tmp_path):
    target_file = tmp_path / "quoted_l_simp_chinese.yml"
    _write_loc_file(
        target_file,
        "l_simp_chinese",
        [("demo.one:0", "坏译文")],
    )

    updated = apply_translation_fix_to_file(target_file, "demo.one:0", '修复 "引号" 文本')

    assert updated is True
    content = target_file.read_text(encoding="utf-8-sig")
    assert 'demo.one:0 "修复 \\"引号\\" 文本"' in content


def test_apply_translation_fix_to_file_matches_base_key(tmp_path):
    target_file = tmp_path / "basekey_l_simp_chinese.yml"
    _write_loc_file(
        target_file,
        "l_simp_chinese",
        [("demo.one:0", "旧文本"), ("demo.two:0", "保持不变")],
    )

    updated = apply_translation_fix_to_file(target_file, "demo.one", "基础键也能更新")

    assert updated is True
    content = target_file.read_text(encoding="utf-8-sig")
    assert 'demo.one:0 "基础键也能更新"' in content
    assert 'demo.two:0 "保持不变"' in content


def test_apply_translation_fix_to_file_returns_false_when_missing_key(tmp_path):
    target_file = tmp_path / "missing_l_simp_chinese.yml"
    _write_loc_file(
        target_file,
        "l_simp_chinese",
        [("demo.one:0", "旧文本")],
    )
    original_content = target_file.read_text(encoding="utf-8-sig")

    updated = apply_translation_fix_to_file(target_file, "demo.unknown:0", "不会写入")

    assert updated is False
    assert target_file.read_text(encoding="utf-8-sig") == original_content
