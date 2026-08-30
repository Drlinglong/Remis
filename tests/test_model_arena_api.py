import json
from pathlib import Path
import sqlite3
from urllib.parse import unquote

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.model_arena_repository import ModelArenaRepository
from scripts.core.services.model_arena_service import ModelArenaService
from scripts.routers import model_arena as model_arena_router
from scripts.schemas.model_arena import CreateModelArenaRunRequest
from scripts.shared import task_state
from scripts.shared.state import tasks


class _ProjectManager:
    def __init__(self, root):
        self.root = root

    async def get_project(self, project_id):
        if project_id != "project-1":
            return None
        return {
            "project_id": project_id,
            "name": "Vic3 Demo",
            "game_id": "vic3",
            "source_language": "en",
            "source_path": str(self.root),
        }

    async def get_project_files(self, project_id):
        return [
            {
                "file_path": str(self.root / "localization" / "english" / "demo.yml"),
                "file_type": "source",
            }
        ]


class _Handler:
    def __init__(self, provider_name, model_id):
        self.provider_name = provider_name
        self.model_id = model_id
        self.client = object()
        self.calls = 0
        self.prompts = []

    def _build_prompt(self, task):
        return (
            "Translate this exact numbered list as JSON.\n"
            + "\n".join(f"{index + 1}. {text}" for index, text in enumerate(task.texts))
        )

    def _call_api(self, client, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        prefix = "甲" if self.provider_name == "lm_studio" else "乙"
        return json.dumps([f"{prefix}{index}" for index in range(1, 4)])

    def _parse_response(self, completion, source_texts, target_lang_code):
        return json.loads(completion)


class _GlossaryManager:
    def __init__(self):
        self.games = []

    async def get_available_glossaries(self, game_id):
        self.games.append(("available", game_id))
        return [{
            "glossary_id": 4,
            "game_id": game_id,
            "name": f"{game_id} Main Glossary",
            "is_main": True,
        }]

    async def get_project_glossary(self, game_id, project_id, project_name):
        self.games.append(("project", game_id))
        return {
            "glossary_id": 9,
            "game_id": game_id,
            "name": f"{project_name} Terms",
            "is_main": False,
        }

    async def get_entries_for_glossary_ids(self, glossary_ids):
        assert glossary_ids == [4, 9]
        return [
            {
                "entry_id": "argentum",
                "glossary_id": 4,
                "translations": {"en": "Argentum-9", "zh-CN": "秘银-9"},
            },
            {
                "entry_id": "project-term",
                "glossary_id": 9,
                "translations": {"en": "Court", "zh-CN": "宫廷"},
            },
        ]


@pytest.fixture
def arena_client(tmp_path, monkeypatch):
    source = tmp_path / "mod" / "localization" / "english"
    source.mkdir(parents=True)
    (source / "demo.yml").write_text(
        '\ufeffl_english:\n a:0 "Hello"\n b:0 "A $VALUE$ choice!"\n c:0 "Argentum-9 powers the court."\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "remis.sqlite"
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO projects (
                project_id, name, game_id, source_path, source_language, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("project-1", "Vic3 Demo", "vic3", str(tmp_path / "mod"), "en", "active"),
        )
    handlers = []
    snapshots = []

    def handler_factory(provider_name, model_name=None, **kwargs):
        snapshots.append(kwargs.get("provider_config_snapshot"))
        handler = _Handler(provider_name, model_name)
        handlers.append(handler)
        return handler

    service = ModelArenaService(
        repository=ModelArenaRepository(str(db_path)),
        project_manager=_ProjectManager(tmp_path / "mod"),
        handler_factory=handler_factory,
        glossary_manager=_GlossaryManager(),
    )
    monkeypatch.setattr(model_arena_router, "model_arena_service", service)
    monkeypatch.setattr(model_arena_router.app_settings, "OUTPUT_DIR", str(tmp_path / "exports"))
    tasks.clear()
    task_state.configure_repository(None)
    app = FastAPI()
    app.include_router(model_arena_router.router)
    with TestClient(app) as client:
        yield client, service, handlers, snapshots
    tasks.clear()


def _draft(client):
    response = client.post(
        "/api/model-arena/runs",
        json={
            "project_id": "project-1",
            "target_lang_code": "zh-CN",
            "sample_size": 3,
            "contestants": [
                {"provider_id": "lm_studio", "model_id": "model-a"},
                {"provider_id": "deepseek", "model_id": "model-b"},
            ],
            "sample_seed": "stable-seed",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_draft_does_not_call_models_and_start_requires_confirmation(arena_client):
    client, _service, handlers, _snapshots = arena_client
    draft = _draft(client)
    assert draft["status"] == "draft"
    assert draft["request_batch_count"] == 1
    assert draft["estimated_request_count"] == 2
    assert handlers == []
    denied = client.post(
        f"/api/model-arena/runs/{draft['run_id']}/start",
        json={"confirmed_model_calls": False, "idempotency_key": "start-1"},
    )
    assert denied.status_code == 409
    assert handlers == []


def test_draft_freezes_initial_translation_glossary_stack(arena_client):
    client, _service, handlers, _snapshots = arena_client
    draft = _draft(client)

    snapshot = draft["settings"]["glossary_snapshot"]
    assert snapshot["enabled"] is True
    assert [item["glossary_id"] for item in snapshot["glossaries"]] == [4, 9]
    assert snapshot["entry_count"] == 2
    assert snapshot["matched_entry_count"] == 2
    assert any(
        "glossary_term" in sample["feature_tags"] for sample in draft["samples"]
    )
    assert handlers == []


async def test_glossary_stack_uses_the_selected_projects_game_without_fallback():
    glossary_manager = _GlossaryManager()
    service = ModelArenaService(
        repository=None,
        project_manager=None,
        glossary_manager=glossary_manager,
    )
    request = CreateModelArenaRunRequest(
        project_id="eu5-project",
        target_lang_code="zh-CN",
        contestants=[
            {"provider_id": "lm_studio", "model_id": "model-a"},
            {"provider_id": "deepseek", "model_id": "model-b"},
        ],
    )

    _entries, snapshot = await service._snapshot_translation_glossaries(
        project={"game_id": "eu5", "name": "EU5 Demo"},
        request=request,
    )

    assert glossary_manager.games == [("available", "eu5"), ("project", "eu5")]
    assert snapshot["glossaries"][0]["name"] == "eu5 Main Glossary"

    with pytest.raises(ValueError, match="no game type"):
        await service._snapshot_translation_glossaries(
            project={"name": "Broken Project"},
            request=request,
        )


def test_unknown_provider_is_rejected_without_silent_substitution(arena_client):
    client, _service, handlers, _snapshots = arena_client
    response = client.post(
        "/api/model-arena/runs",
        json={
            "project_id": "project-1",
            "target_lang_code": "zh-CN",
            "sample_size": 3,
            "contestants": [
                {"provider_id": "lm_studio", "model_id": "model-a"},
                {"provider_id": "typo-provider", "model_id": "model-b"},
            ],
        },
    )
    assert response.status_code == 409
    assert "never substitutes another provider" in response.json()["detail"]
    assert handlers == []


def test_anonymous_vote_complete_reveal_and_safe_export(arena_client):
    client, service, handlers, snapshots = arena_client
    draft = _draft(client)
    run_id = draft["run_id"]
    started = client.post(
        f"/api/model-arena/runs/{run_id}/start",
        json={"confirmed_model_calls": True, "idempotency_key": "start-1"},
    )
    assert started.status_code == 200, started.text
    assert len(handlers) == 2
    assert snapshots == [
        draft["contestants"][0]["config_snapshot"],
        draft["contestants"][1]["config_snapshot"],
    ]
    assert sum(handler.calls for handler in handlers) == 2
    assert all("'Argentum-9' → '秘银-9'" in handler.prompts[0] for handler in handlers)
    assert all("'Court' → '宫廷'" in handler.prompts[0] for handler in handlers)

    judging = client.get(f"/api/model-arena/runs/{run_id}").json()
    assert judging["status"] == "voting", [
        [item.get("failure_code") for item in judging["contestants"]],
        [(handler.provider_name, handler.calls) for handler in handlers],
    ]
    assert all("provider_id" not in item for item in judging["contestants"])
    assert all("contestant_id" not in item for item in judging["outputs"])
    assert judging["requests"] == []

    for sample in judging["samples"]:
        output = next(
            item for item in judging["outputs"] if item["sample_id"] == sample["sample_id"]
        )
        vote = client.put(
            f"/api/model-arena/runs/{run_id}/samples/{sample['sample_id']}/vote",
            json={
                "verdict": "winner",
                "winner_output_id": output["output_id"],
                "reason_codes": ["faithful", "concise"],
                "note": "路径 C:\\private\\demo.yml token=secret-value",
            },
        )
        assert vote.status_code == 200, vote.text

    completed = client.post(f"/api/model-arena/runs/{run_id}/complete")
    assert completed.status_code == 200, completed.text
    revealed = completed.json()
    assert revealed["status"] == "completed"
    assert {item["provider_id"] for item in revealed["contestants"]} == {
        "lm_studio",
        "deepseek",
    }
    assert sum(
        item["selected_count"] for item in revealed["results"]["contestants"]
    ) == 3

    preview = client.get(
        f"/api/model-arena/runs/{run_id}/export-preview",
        params={"mode": "evidence"},
    )
    assert preview.status_code == 200, preview.text
    serialized = json.dumps(preview.json(), ensure_ascii=False).lower()
    assert "entry_key" not in serialized
    assert "relative_file_path" not in serialized
    assert "secret-value" not in serialized
    assert "c:\\private\\demo.yml" not in serialized
    assert "completion_text_before_parse" in serialized
    assert "system_instruction" in serialized
    downloaded = client.post(
        f"/api/model-arena/runs/{run_id}/export",
        json={"approved": True, "mode": "evidence"},
    )
    assert downloaded.status_code == 200
    assert downloaded.json() == preview.json()
    export_path = Path(unquote(downloaded.headers["x-remis-export-path"]))
    assert export_path.is_file()
    assert json.loads(export_path.read_text(encoding="utf-8")) == preview.json()


def test_start_is_idempotent_and_delete_requires_confirmation(arena_client):
    client, _service, handlers, _snapshots = arena_client
    draft = _draft(client)
    run_id = draft["run_id"]
    body = {"confirmed_model_calls": True, "idempotency_key": "same-key"}
    first = client.post(f"/api/model-arena/runs/{run_id}/start", json=body)
    second = client.post(f"/api/model-arena/runs/{run_id}/start", json=body)
    assert first.status_code == second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert len(handlers) == 2

    denied = client.delete(f"/api/model-arena/runs/{run_id}")
    assert denied.status_code == 409
    deleted = client.delete(
        f"/api/model-arena/runs/{run_id}", params={"confirmed": "true"}
    )
    assert deleted.status_code == 204
    assert client.get(f"/api/model-arena/runs/{run_id}").status_code == 404


def test_retry_calls_only_the_failed_contestant_after_fresh_confirmation(
    arena_client,
):
    client, service, _handlers, _snapshots = arena_client
    attempts = {"lm_studio": 0, "deepseek": 0}

    class _FlakyHandler(_Handler):
        def _call_api(self, client, prompt):
            attempts[self.provider_name] += 1
            if self.provider_name == "deepseek" and attempts["deepseek"] == 1:
                raise RuntimeError("temporary provider failure")
            return super()._call_api(client, prompt)

    service.handler_factory = (
        lambda provider_name, model_name=None, **_kwargs: _FlakyHandler(
            provider_name, model_name
        )
    )
    draft = _draft(client)
    run_id = draft["run_id"]
    started = client.post(
        f"/api/model-arena/runs/{run_id}/start",
        json={"confirmed_model_calls": True, "idempotency_key": "initial"},
    )
    assert started.status_code == 200
    assert client.get(f"/api/model-arena/runs/{run_id}").json()["status"] == "partial_failed"
    assert attempts == {"lm_studio": 1, "deepseek": 1}

    denied = client.post(
        f"/api/model-arena/runs/{run_id}/retry-failures",
        json={"confirmed_model_calls": False, "idempotency_key": "retry-1"},
    )
    assert denied.status_code == 409
    retried = client.post(
        f"/api/model-arena/runs/{run_id}/retry-failures",
        json={"confirmed_model_calls": True, "idempotency_key": "retry-1"},
    )
    assert retried.status_code == 200, retried.text
    judging = client.get(f"/api/model-arena/runs/{run_id}").json()
    assert judging["status"] == "voting"
    assert attempts == {"lm_studio": 1, "deepseek": 2}
