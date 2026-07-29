import json

import pytest
from fastapi.testclient import TestClient
from scripts.web_server import app
from scripts.routers import glossary as glossary_router
from scripts.routers.glossary import (
    _transform_entry_to_storage_format,
    _transform_storage_to_frontend_format,
    glossary_manager,
    task_state,
)

client = TestClient(app)

def test_get_glossaries():
    # Assuming 'stellaris' is a valid game_id
    response = client.get("/api/glossaries/stellaris")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_glossary_overview_route_is_not_captured_as_game_id(monkeypatch):
    expected = {
        "summary": {"game_count": 1, "glossary_count": 2, "term_count": 3},
        "glossaries": [],
    }

    async def fake_overview():
        return expected

    monkeypatch.setattr(glossary_manager, "get_glossary_overview", fake_overview)

    response = client.get("/api/glossaries/overview")

    assert response.status_code == 200
    assert response.json() == expected


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        ("/api/glossary", {"game_id": "vic3", "name": "Core terminology"}),
        (
            "/api/glossary/file",
            {"game_id": "vic3", "file_name": "Core terminology"},
        ),
    ],
)
def test_create_glossary_uses_asset_name_and_keeps_legacy_payload_compatible(
    monkeypatch,
    route,
    payload,
):
    async def fake_create(game_id, name):
        assert game_id == "vic3"
        assert name == "Core terminology"
        return True

    monkeypatch.setattr(glossary_manager, "create_glossary", fake_create)

    response = client.post(route, json=payload)

    assert response.status_code == 201
    assert response.json() == {
        "message": "Glossary created successfully",
        "name": "Core terminology",
    }


def test_duplicate_glossary_route_returns_created_copy(monkeypatch):
    expected = {
        "glossary_id": 12,
        "game_id": "stellaris",
        "name": "Review Copy",
        "entry_count": 4,
        "copied_from": {
            "glossary_id": 7,
            "game_id": "stellaris",
            "name": "Source",
        },
    }

    async def fake_duplicate(glossary_id, target_name):
        assert glossary_id == 7
        assert target_name == "Review Copy"
        return expected

    monkeypatch.setattr(glossary_manager, "duplicate_glossary", fake_duplicate)

    response = client.post("/api/glossary/file/7/duplicate", json={"name": " Review Copy "})

    assert response.status_code == 201
    assert response.json() == expected


def test_duplicate_glossary_route_reports_missing_source(monkeypatch):
    async def fake_duplicate(_glossary_id, _target_name):
        return None

    monkeypatch.setattr(glossary_manager, "duplicate_glossary", fake_duplicate)

    response = client.post("/api/glossary/file/404/duplicate", json={"name": "Copy"})

    assert response.status_code == 404


def test_update_glossary_metadata_route_returns_updated_identity(monkeypatch):
    expected = {
        "glossary_id": 7,
        "game_id": "vic3",
        "name": "Remis Demo Terms",
        "description": "Terms reviewed by the localization team.",
        "kind": "project",
        "updated_at": "2026-07-24T12:00:00",
    }

    async def fake_update(glossary_id, *, name, description, kind, project_ids):
        assert glossary_id == 7
        assert name == "Remis Demo Terms"
        assert description == "Terms reviewed by the localization team."
        assert kind == "project"
        assert project_ids == ["project-1", "project-2"]
        return expected

    monkeypatch.setattr(glossary_manager, "update_glossary_metadata", fake_update)

    response = client.put(
        "/api/glossary/file/7",
        json={
            "name": "Remis Demo Terms",
            "description": "Terms reviewed by the localization team.",
            "kind": "project",
            "project_ids": ["project-1", "project-2"],
        },
    )

    assert response.status_code == 200
    assert response.json() == expected


def test_update_glossary_metadata_route_reports_missing_glossary(monkeypatch):
    async def fake_update(_glossary_id, *, name, description, kind, project_ids):
        return None

    monkeypatch.setattr(glossary_manager, "update_glossary_metadata", fake_update)

    response = client.put(
        "/api/glossary/file/404",
        json={"name": "Missing", "description": ""},
    )

    assert response.status_code == 404


def test_batch_delete_preview_and_execution_routes(monkeypatch):
    preview = {
        "glossary_count": 2,
        "term_count": 9,
        "glossaries": [],
        "main_glossaries": [],
        "project_glossaries": [],
        "bound_projects": [],
        "missing_glossary_ids": [],
    }

    async def fake_preview(glossary_ids):
        assert glossary_ids == [3, 4]
        return preview

    async def fake_delete(glossary_ids, **kwargs):
        assert glossary_ids == [3, 4]
        assert kwargs == {
            "confirm_main_glossaries": True,
            "confirm_project_bindings": False,
        }
        return {
            "deleted_glossary_ids": [3, 4],
            "deleted_glossary_count": 2,
            "deleted_term_count": 9,
            "removed_project_binding_count": 0,
        }

    monkeypatch.setattr(glossary_manager, "get_batch_delete_impact", fake_preview)
    monkeypatch.setattr(glossary_manager, "batch_delete_glossaries", fake_delete)

    preview_response = client.post(
        "/api/glossaries/batch-delete/preview",
        json={"glossary_ids": [3, 4]},
    )
    delete_response = client.post(
        "/api/glossaries/batch-delete",
        json={
            "glossary_ids": [3, 4],
            "confirm_main_glossaries": True,
            "confirm_project_bindings": False,
        },
    )

    assert preview_response.status_code == 200
    assert preview_response.json() == preview
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_term_count"] == 9


def test_merge_preview_and_execution_use_unified_task_contract(monkeypatch):
    preview = {
        "target_name": "Merged",
        "unique_term_count": 4,
        "conflict_count": 1,
    }
    result = {
        "glossary_id": 22,
        "game_id": "stellaris",
        "name": "Merged",
        "merged_from": [{"glossary_id": 1}, {"glossary_id": 2}],
        "created_entry_count": 3,
        "updated_entry_count": 0,
    }
    created_tasks = []
    updated_tasks = []

    async def fake_preview(**kwargs):
        assert kwargs["glossary_ids"] == [1, 2]
        return preview

    async def fake_merge(**kwargs):
        assert kwargs["target_name"] == "Merged"
        return result

    monkeypatch.setattr(glossary_manager, "preview_glossary_merge", fake_preview)
    monkeypatch.setattr(glossary_manager, "merge_glossaries", fake_merge)
    monkeypatch.setattr(task_state, "create_task", lambda task_id, **kwargs: created_tasks.append((task_id, kwargs)))
    monkeypatch.setattr(task_state, "init_progress", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(task_state, "update_task", lambda task_id, **kwargs: updated_tasks.append((task_id, kwargs)))

    payload = {
        "glossary_ids": [1, 2],
        "target_mode": "new",
        "target_name": "Merged",
        "target_glossary_id": None,
        "conflict_strategy": "skip_conflicts",
    }
    preview_response = client.post("/api/glossaries/merge/preview", json=payload)
    start_response = client.post("/api/glossaries/merge", json=payload)

    assert preview_response.status_code == 200
    assert start_response.status_code == 200
    assert start_response.json()["preview"] == preview
    assert created_tasks[0][1]["fields"]["kind"] == "glossary_merge"
    assert created_tasks[0][1]["fields"]["blocking"] is True
    assert any(update[1].get("status") == "completed" for update in updated_tasks)


def test_health_check_is_read_only_task_and_ai_requires_explicit_approval(monkeypatch):
    report = {
        "score": 90,
        "issue_count": 2,
        "issues": [],
        "mutations_applied": False,
    }
    created_tasks = []
    updated_tasks = []

    async def fake_health(glossary_ids, *, target_lang=None):
        assert glossary_ids == [7]
        assert target_lang == "zh-CN"
        return dict(report)

    monkeypatch.setattr(glossary_manager, "check_glossary_health", fake_health)
    monkeypatch.setattr(task_state, "create_task", lambda task_id, **kwargs: created_tasks.append((task_id, kwargs)))
    monkeypatch.setattr(task_state, "init_progress", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(task_state, "update_task", lambda task_id, **kwargs: updated_tasks.append((task_id, kwargs)))

    response = client.post("/api/glossaries/health-check", json={
        "glossary_ids": [7],
        "target_lang": "zh-CN",
        "include_ai_advice": False,
    })
    rejected_ai = client.post("/api/glossaries/health-check", json={
        "glossary_ids": [7],
        "target_lang": "zh-CN",
        "include_ai_advice": True,
        "confirm_model_usage": False,
        "api_provider": "openai",
    })

    assert response.status_code == 200
    assert response.json()["mutations_applied"] is False
    assert created_tasks[0][1]["fields"]["kind"] == "glossary_health_check"
    assert created_tasks[0][1]["fields"]["blocking"] is False
    assert created_tasks[0][1]["fields"]["source_route"] == "/glossary-manager"
    assert any(update[1].get("status") == "completed" for update in updated_tasks)
    assert rejected_ai.status_code == 422


def test_health_check_ai_uses_dynamic_batches_and_persists_entry_advice(monkeypatch):
    report = {
        "score": 94,
        "entry_count": 2,
        "issue_count": 2,
        "target_lang": "en",
        "issues": [{
            "code": "missing_translation",
            "severity": "warning",
            "count": 2,
            "message": "Entries with missing translations",
            "items": [
                {
                    "entry_id": "term-1",
                    "glossary_id": 7,
                    "glossary_name": "Test",
                    "game_id": "vic3",
                    "source": "泰尔紫",
                    "current_translation": None,
                    "detail": "Missing translation for en.",
                },
                {
                    "entry_id": "term-2",
                    "glossary_id": 7,
                    "glossary_name": "Test",
                    "game_id": "vic3",
                    "source": "光复罗马",
                    "current_translation": None,
                    "detail": "Missing translation for en.",
                },
            ],
        }],
        "mutations_applied": False,
    }
    updated_tasks = []

    async def fake_health(_glossary_ids, *, target_lang=None):
        assert target_lang == "en"
        return {
            **report,
            "issues": [{**report["issues"][0], "items": list(report["issues"][0]["items"])}],
        }

    class FakeHandler:
        def generate_with_messages(self, messages, temperature=0.1):
            payload = json.loads(messages[1]["content"])
            return json.dumps([
                {
                    "case_id": case["case_id"],
                    "entry_id": case["entry_id"],
                    "issue_code": case["issue_code"],
                    "suggested_source": None,
                    "suggested_translation": f"{case['source']} translated",
                    "recommendation": "Use this English translation.",
                    "rationale": "This is a direct terminology translation.",
                    "priority": "high",
                    "confidence": 0.9,
                }
                for case in payload["cases"]
            ], ensure_ascii=False)

    monkeypatch.setattr(glossary_manager, "check_glossary_health", fake_health)
    monkeypatch.setattr(glossary_router, "get_handler", lambda *_args, **_kwargs: FakeHandler())
    monkeypatch.setattr(task_state, "create_task", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(task_state, "init_progress", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        task_state,
        "update_task",
        lambda task_id, **kwargs: updated_tasks.append((task_id, kwargs)),
    )

    response = client.post("/api/glossaries/health-check", json={
        "glossary_ids": [7],
        "target_lang": "en",
        "include_ai_advice": True,
        "confirm_model_usage": True,
        "api_provider": "openai",
        "model_name": "test-model",
        "concurrency_limit": 2,
    })

    assert response.status_code == 200
    assert response.json()["ai_review_plan"]["case_count"] == 2
    assert response.json()["ai_review_plan"]["batch_sizes"] == [2]
    completed = next(
        update[1]
        for update in updated_tasks
        if update[1].get("status") == "completed"
    )
    metadata = completed["fields"]["result"]["metadata"]
    assert metadata["ai_review_plan"]["batch_count"] == 1
    assert [item["entry_id"] for item in metadata["ai_advice"]] == [
        "term-1",
        "term-2",
    ]


def test_health_check_preserves_deterministic_report_when_optional_ai_fails(monkeypatch):
    report = {
        "score": 94,
        "entry_count": 1,
        "issue_count": 1,
        "target_lang": "en",
        "issues": [{
            "code": "missing_translation",
            "severity": "warning",
            "count": 1,
            "message": "Entries with missing translations",
            "items": [{
                "entry_id": "term-1",
                "glossary_id": 7,
                "glossary_name": "Test",
                "game_id": "vic3",
                "source": "泰尔紫",
                "current_translation": None,
                "detail": "Missing translation for en.",
            }],
        }],
        "mutations_applied": False,
    }
    updated_tasks = []

    async def fake_health(_glossary_ids, *, target_lang=None):
        assert target_lang == "en"
        return report

    class FailingHandler:
        def generate_with_messages(self, *_args, **_kwargs):
            raise RuntimeError('provider payload: {"error":"No models loaded"}')

    monkeypatch.setattr(glossary_manager, "check_glossary_health", fake_health)
    monkeypatch.setattr(glossary_router, "get_handler", lambda *_args, **_kwargs: FailingHandler())
    monkeypatch.setattr(task_state, "create_task", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(task_state, "init_progress", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        task_state,
        "update_task",
        lambda task_id, **kwargs: updated_tasks.append((task_id, kwargs)),
    )

    response = client.post("/api/glossaries/health-check", json={
        "glossary_ids": [7],
        "target_lang": "en",
        "include_ai_advice": True,
        "confirm_model_usage": True,
        "api_provider": "openai",
        "model_name": "test-model",
    })

    assert response.status_code == 200
    completed = next(
        update[1]
        for update in updated_tasks
        if update[1].get("status") == "completed"
    )
    assert "provider payload" not in completed["message"]
    assert "provider payload" not in completed["append_log"]
    assert completed["progress"]["warning_count"] == 1
    assert completed["progress"]["error_count"] == 0
    result = completed["fields"]["result"]
    assert result["types"] == ["glossary_health_report"]
    assert result["metadata"]["score"] == 94
    assert result["metadata"]["ai_review_status"] == "failed"
    assert result["metadata"]["completion_outcome"] == "partial_success"
    assert result["metadata"]["ai_review_error"] == "GlossaryHealthReviewError"
    assert "No models loaded" not in str(result)


def test_search_glossary():
    response = client.post("/api/glossary/search", json={
        "query": "Empire",
        "scope": "game",
        "game_id": "stellaris"
    })
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "entries" in data
    assert isinstance(data["entries"], list)


def test_frontend_source_prefers_canonical_source_text_metadata():
    entry = _transform_storage_to_frontend_format({
        "entry_id": "term-1",
        "translations": {"zh-CN": "泰尔紫"},
        "raw_metadata": {
            "source_text": "泰尔紫 (Tyrian Purple)",
            "source_lang": "zh-CN",
            "target_lang": "zh-CN",
        },
    })

    assert entry["source"] == "泰尔紫 (Tyrian Purple)"


def test_storage_keeps_same_language_source_separate_from_translation():
    entry = _transform_entry_to_storage_format({
        "id": "term-1",
        "source": "泰尔紫 (Tyrian Purple)",
        "translations": {"zh-CN": "泰尔紫"},
        "metadata": {
            "source_lang": "zh-CN",
            "target_lang": "zh-CN",
        },
    })

    assert entry["translations"] == {"zh-CN": "泰尔紫"}
    assert entry["metadata"]["source_text"] == "泰尔紫 (Tyrian Purple)"
