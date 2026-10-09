import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.core.archive_manager import ArchiveManager
from scripts.core.batch_apply_archive import ensure_source_version, source_files
from scripts.core.batch_collection import collect_results
from scripts.core.batch_project_guard import BatchProjectGuard
from scripts.core.agent_batch_service import AgentBatchService
from scripts.core.batch_artifacts import BatchArtifacts
from scripts.core.batch_repository import BatchConflict, BatchRepository
from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.task_repository import TaskRepository
from scripts.schemas.agent_batch import BatchPlanRequest, BatchStartRequest
from scripts.routers import agent_batch as agent_batch_router


class FakeProjectManager:
    def __init__(self, project_id, source_root, source_file):
        self.project = {
            "project_id": project_id,
            "name": "Batch workflow fixture",
            "game_id": "surviving_mars",
            "source_language": "en",
            "source_path": str(source_root),
        }
        self.files = [{"file_id": "source-1", "file_path": str(source_file), "file_type": "source"}]
        self.registered_paths = []
        self.fail_next_registration = False

    async def get_project(self, project_id):
        return dict(self.project) if project_id == self.project["project_id"] else None

    async def get_project_files(self, project_id):
        return [dict(item) for item in self.files] if project_id == self.project["project_id"] else []

    async def add_translation_path(self, project_id, translation_path):
        assert project_id == self.project["project_id"]
        if self.fail_next_registration:
            self.fail_next_registration = False
            raise OSError("simulated translation path registration failure")
        self.registered_paths.append(translation_path)
        for path in sorted(Path(translation_path).rglob("*.csv")):
            self.files.append({
                "file_id": f"translated-{len(self.files)}",
                "file_path": str(path),
                "file_type": "translation",
            })


class FakeTransport:
    def __init__(self, *, fail_first_suffix=None, fail_submission=False):
        self.fail_first_suffix = fail_first_suffix
        self.fail_submission = fail_submission
        self.catalog_calls = []
        self.submissions = []
        self.remote_batches = {}

    async def model_endpoints(self, model):
        self.catalog_calls.append(model)
        return {"endpoints": [{"name": "fake-endpoint"}]}

    async def submit(self, payload):
        self.submissions.append(payload)
        if self.fail_submission:
            raise TimeoutError("simulated connection loss")
        batch_number = len(self.submissions)
        results = []
        for request in payload["requests"]:
            custom_id = request["custom_id"]
            if batch_number == 1 and custom_id.endswith(self.fail_first_suffix or "\\0"):
                results.append({"custom_id": custom_id, "error": {"code": "simulated_failure"}})
                continue
            user_payload = json.loads(request["body"]["messages"][1]["content"])
            translations = {
                entry["id"]: f"火星译文{entry['key']}"
                for entry in user_payload["entries"]
            }
            results.append({
                "custom_id": custom_id,
                "response": {
                    "status_code": 200,
                    "body": {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"translations": translations}, ensure_ascii=False)}}]},
                },
            })
        remote_id = f"remote-{batch_number}"
        remote = {"id": remote_id, "status": "completed", "results": results,
                  "usage": {"total_tokens": 12}, "request_counts": {"total": len(results)}}
        self.remote_batches[remote_id] = remote
        return {"id": remote_id, "status": "queued"}

    async def retrieve(self, remote_id):
        return self.remote_batches[remote_id]


@pytest.fixture
def batch_environment(tmp_path, monkeypatch):
    import scripts.core.archive_manager as archive_module

    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "Game.csv"
    source_file.write_text(
        "ID,Text,Translation,VoiceActor,Context\n"
        "1001,Concrete source,,voice-a,context-a\n"
        "1002,Second source,,voice-b,context-b\n",
        encoding="utf-8",
        newline="",
    )
    monkeypatch.setattr(archive_module, "MODS_CACHE_DB_PATH", str(tmp_path / "archive.sqlite3"))
    archive = ArchiveManager()
    assert archive.initialize_database()
    manager = FakeProjectManager("project-mars", source_root, source_file)
    repository_path = tmp_path / "batch.sqlite3"
    artifacts_path = tmp_path / "artifacts"
    repository = BatchRepository(repository_path)
    artifacts = BatchArtifacts(artifacts_path)
    transport = FakeTransport()
    output_root = tmp_path / "batch-outputs"
    task_db = tmp_path / "remis-main.sqlite3"
    assert migrate_main_database(str(task_db))
    task_repository = TaskRepository(str(task_db))
    project_guard = BatchProjectGuard(task_repository)

    def service(repo=None, wire=None, project_manager=None, custom_output_root=None):
        return AgentBatchService(
            repo or BatchRepository(repository_path),
            BatchArtifacts(artifacts_path),
            wire or transport,
            project_manager or manager,
            archive,
            custom_output_root or output_root,
            project_guard,
        )

    yield {
        "tmp_path": tmp_path,
        "source_file": source_file,
        "manager": manager,
        "archive": archive,
        "repository": repository,
        "artifacts": artifacts,
        "transport": transport,
        "task_repository": task_repository,
        "service": service,
    }
    archive.close()



@pytest.fixture
async def real_project_manager(tmp_path, batch_environment):
    from sqlmodel import SQLModel

    from scripts.core.db_manager import db_manager
    from scripts.core.project_manager import ProjectManager
    from scripts.core.repositories.project_repository import ProjectRepository
    from scripts.core.services.file_service import FileService
    from scripts.core.services.translation_archive_service import TranslationArchiveService

    old_db_path = db_manager.db_path
    old_engine = getattr(db_manager, "_async_engine", None)
    old_sync_engine = getattr(db_manager, "_sync_engine", None)
    if old_engine is not None:
        await old_engine.dispose()
        del db_manager._async_engine
    if old_sync_engine is not None:
        old_sync_engine.dispose()
        del db_manager._sync_engine

    project_db_path = str(tmp_path / "projects.sqlite3")
    db_manager.db_path = project_db_path
    engine = db_manager.get_async_engine()
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    repository = ProjectRepository(project_db_path)
    manager = ProjectManager(
        file_service=FileService(),
        project_repository=repository,
        archive_service=TranslationArchiveService(am=batch_environment["archive"]),
        db_path=project_db_path,
    )
    try:
        yield manager
    finally:
        await engine.dispose()
        if hasattr(db_manager, "_async_engine"):
            del db_manager._async_engine
        if hasattr(db_manager, "_sync_engine"):
            db_manager._sync_engine.dispose()
            del db_manager._sync_engine
        db_manager.db_path = old_db_path

def plan_request(*, project_id="project-mars", file_ids=None):
    values = {
        "project_id": project_id,
        "file_ids": file_ids or ["source-1"],
        "target_locale": "zh-TW",
        "game_language_slot": "Schinese",
        "model": "test/provider-model",
        "provider_only": [],
        "style_guide": "Keep the game's concise UI tone.",
        "reasoning": {},
        "group_size": 1,
        "max_group_chars": 12000,
    }
    # The service's explicit no-terms mode is part of the current workflow schema.
    if "translation_context_mode" in BatchPlanRequest.model_fields:
        values["translation_context_mode"] = "none"
    return BatchPlanRequest(**values)


def start_request(plan_id, key="request-1"):
    return BatchStartRequest(plan_id=plan_id, idempotency_key=key, approved=True)


@pytest.mark.asyncio
async def test_plan_submit_restart_collect_and_apply_registers_zh_tw_with_schinese_slot(batch_environment):
    service = batch_environment["service"]()
    plan = await service.plan(plan_request())

    assert plan["settings"]["target_locale"] == "zh-TW"
    assert plan["settings"]["game_language_slot"] == "Schinese"
    assert plan["request_count"] == 2
    assert plan["paid_calls"] == 0

    job = await service.start(start_request(plan["id"]))
    assert job["remote_id"] == "remote-1"
    assert job["submission_state"] == "submitted"
    assert len(batch_environment["transport"].submissions) == 1

    # Simulate a process restart: repository and artifact objects are reopened from disk.
    restarted = batch_environment["service"]()
    restored = restarted.get(job["id"])
    assert restored["remote_id"] == job["remote_id"]
    repeated = await restarted.start(start_request(plan["id"]))
    assert repeated["id"] == job["id"]
    assert len(batch_environment["transport"].submissions) == 1

    collected = await restarted.collect(job["id"])
    assert collected["collection"]["failed_custom_ids"] == []
    assert len(collected["collection"]["translations"]) == 2
    assert collected["collection"]["complete_file_ids"] == ["source-1"]

    apply_plan = await restarted.apply_plan(job["id"])
    applied = await restarted.apply(job["id"], apply_plan["id"], approved=True)
    assert applied["apply_status"] == "applied"
    assert batch_environment["manager"].registered_paths
    output_file = Path(applied["output_paths"][0]) / "Game.csv"
    assert output_file.is_file()
    assert "1001,Concrete source,火星译文1001,voice-a,context-a" in output_file.read_text(encoding="utf-8")

    manifest = json.loads((output_file.parent.parent / ".remis-batch-output.json").read_text(encoding="utf-8"))
    assert manifest["target_locale"] == "zh-TW"
    assert manifest["game_language_slot"] == "Schinese"
    rows = batch_environment["archive"].connection.execute(
        "SELECT t.language_code,t.translated_text FROM translated_entries t "
        "JOIN source_entries s ON s.source_entry_id=t.source_entry_id ORDER BY s.entry_key"
    ).fetchall()
    assert [(row["language_code"], row["translated_text"]) for row in rows] == [
        ("zh-TW", "火星译文1001"), ("zh-TW", "火星译文1002")
    ]
    registered = await batch_environment["manager"].get_project_files("project-mars")
    assert any(row["file_type"] == "translation" and row["file_path"] == str(output_file) for row in registered)


@pytest.mark.asyncio
async def test_unknown_submission_is_persisted_and_same_key_does_not_resubmit(batch_environment):
    transport = FakeTransport(fail_submission=True)
    service = batch_environment["service"](wire=transport)
    plan = await service.plan(plan_request())
    request = start_request(plan["id"], "uncertain-submit")

    first = await service.start(request)
    assert first["submission_state"] == "submission_unknown"
    assert first["diagnostic"]["code"] == "submission_unknown"
    assert len(transport.submissions) == 1

    after_restart = batch_environment["service"](wire=transport)
    same_key = await after_restart.start(request)
    assert same_key["id"] == first["id"]
    assert same_key["submission_state"] == "submission_unknown"
    assert len(transport.submissions) == 1


@pytest.mark.asyncio
async def test_retry_plan_merges_prior_successes_with_failed_request_results(batch_environment):
    transport = FakeTransport(fail_first_suffix=":1")
    service = batch_environment["service"](wire=transport)
    plan = await service.plan(plan_request())
    job = await service.start(start_request(plan["id"]))
    first = await service.collect(job["id"])

    assert len(first["collection"]["translations"]) == 1
    assert len(first["collection"]["failed_custom_ids"]) == 1
    retry_plan = await service.retry_plan(job["id"], first["collection"]["failed_custom_ids"])
    assert retry_plan["entry_count"] == 1

    retry_job = await service.start(start_request(retry_plan["id"], "retry-request"))
    retried = await service.collect(retry_job["id"])

    assert retried["collection"]["failed_custom_ids"] == []
    assert retried["collection"]["complete_file_ids"] == ["source-1"]
    assert len(retried["collection"]["translations"]) == 2
    assert set(retried["collection"]["translations"].values()) == {
        "火星译文1001", "火星译文1002"
    }


@pytest.mark.asyncio
async def test_source_revision_change_blocks_submission_before_transport(batch_environment):
    service = batch_environment["service"]()
    plan = await service.plan(plan_request())
    batch_environment["source_file"].write_text(
        "ID,Text,Translation,VoiceActor,Context\n"
        "1001,Changed source,,voice-a,context-a\n"
        "1002,Second source,,voice-b,context-b\n",
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(BatchConflict) as caught:
        await service.start(start_request(plan["id"]))

    assert caught.value.code == "source_revision_conflict"
    assert batch_environment["transport"].submissions == []




def make_api_client(environment):
    app = FastAPI()
    app.include_router(agent_batch_router.router)
    app.dependency_overrides[agent_batch_router.get_batch_service] = environment["service"]
    return TestClient(app)


def term_request(*, game_id="surviving_mars", locale="zh-TW", version="terms-v1", translation="火星"):
    return {
        "game_id": game_id,
        "locale": locale,
        "version": version,
        "maturity": "provisional",
        "approved": True,
        "terms": [{
            "concept_id": "planet.mars",
            "source": "Mars",
            "translation": translation,
            "sense": "The planet, not a project or mission name.",
            "aliases": ["the Red Planet"],
            "context_keys": ["1001"],
            "evidence_refs": ["test-evidence-1"],
            "reviewer": "test reviewer",
            "review_dimensions": ["meaning"],
            "unverified_dimensions": ["official-game-style"],
        }],
    }


def make_plan_body(*, term_release_id=None, translation_context_mode="none", allow_provisional_terms=False):
    body = plan_request().model_dump()
    body.update(
        translation_context_mode=translation_context_mode,
        allow_provisional_terms=allow_provisional_terms,
    )
    if term_release_id is not None:
        body["term_release_id"] = term_release_id
    return body


@pytest.mark.asyncio
async def test_batch_job_routes_enforce_approval_and_complete_plan_submit_collect_apply(batch_environment):
    environment = batch_environment
    with make_api_client(environment) as client:
        planned = client.post("/api/agent/batch-jobs/plan", json=make_plan_body())
        assert planned.status_code == 200
        plan = planned.json()
        assert plan["settings"]["target_locale"] == "zh-TW"
        assert plan["settings"]["game_language_slot"] == "Schinese"

        denied = client.post("/api/agent/batch-jobs", json={
            "plan_id": plan["id"], "idempotency_key": "http-approval", "approved": False,
        })
        assert denied.status_code == 409
        assert denied.json()["detail"]["code"] == "approval_required"
        assert environment["transport"].submissions == []

        started = client.post("/api/agent/batch-jobs", json={
            "plan_id": plan["id"], "idempotency_key": "http-approval", "approved": True,
        })
        assert started.status_code == 200
        job = started.json()
        duplicate = client.post("/api/agent/batch-jobs", json={
            "plan_id": plan["id"], "idempotency_key": "http-approval", "approved": True,
        })
        assert duplicate.status_code == 200
        assert duplicate.json()["id"] == job["id"]
        assert len(environment["transport"].submissions) == 1

        collected = client.post(f"/api/agent/batch-jobs/{job['id']}/collect", json={})
        assert collected.status_code == 200
        assert collected.json()["collection"]["complete_file_ids"] == ["source-1"]
        apply_plan = client.post(f"/api/agent/batch-jobs/{job['id']}/apply/plan", json={})
        assert apply_plan.status_code == 200
        denied_apply = client.post(f"/api/agent/batch-jobs/{job['id']}/apply", json={
            "apply_plan_id": apply_plan.json()["id"], "approved": False,
        })
        assert denied_apply.status_code == 409
        assert denied_apply.json()["detail"]["code"] == "approval_required"
        applied = client.post(f"/api/agent/batch-jobs/{job['id']}/apply", json={
            "apply_plan_id": apply_plan.json()["id"], "approved": True,
        })
        assert applied.status_code == 200
        assert applied.json()["apply_status"] == "applied"

    tasks = environment["task_repository"].list_tasks(include_events=False)
    apply_task = next(task for task in tasks if task.get("agent_job_kind") == "batch_apply")
    assert apply_task["status"] == "completed"
    assert environment["task_repository"].get_project_lock("project-mars") is None


def test_term_release_routes_are_idempotent_immutable_and_require_identity_and_ack(batch_environment):
    with make_api_client(batch_environment) as client:
        first = client.post("/api/agent/term-releases", json=term_request())
        assert first.status_code == 200
        repeated = client.post("/api/agent/term-releases", json=term_request())
        assert repeated.status_code == 200
        assert repeated.json()["id"] == first.json()["id"]

        changed = client.post("/api/agent/term-releases", json=term_request(translation="红色星球"))
        assert changed.status_code == 409
        assert changed.json()["detail"]["code"] == "immutable_term_release"

        wrong_game = client.post("/api/agent/term-releases", json=term_request(
            game_id="rimworld", version="wrong-game-v1",
        )).json()
        wrong_locale = client.post("/api/agent/term-releases", json=term_request(
            locale="zh-CN", version="wrong-locale-v1",
        )).json()
        for release in (wrong_game, wrong_locale):
            mismatch = client.post("/api/agent/batch-jobs/plan", json=make_plan_body(
                term_release_id=release["id"], translation_context_mode="term_release",
                allow_provisional_terms=True,
            ))
            assert mismatch.status_code == 409
            assert mismatch.json()["detail"]["code"] == "term_release_identity_conflict"

        unacknowledged = client.post("/api/agent/batch-jobs/plan", json=make_plan_body(
            term_release_id=first.json()["id"], translation_context_mode="term_release",
        ))
        assert unacknowledged.status_code == 409
        assert unacknowledged.json()["detail"]["code"] == "provisional_terms_require_choice"

        acknowledged = client.post("/api/agent/batch-jobs/plan", json=make_plan_body(
            term_release_id=first.json()["id"], translation_context_mode="term_release",
            allow_provisional_terms=True,
        ))
        assert acknowledged.status_code == 200
        assert acknowledged.json()["term_release"]["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_failed_registration_recovers_after_archive_commit_without_resubmitting(batch_environment):
    environment = batch_environment
    with make_api_client(environment) as client:
        plan = client.post("/api/agent/batch-jobs/plan", json=make_plan_body()).json()
        job = client.post("/api/agent/batch-jobs", json={
            "plan_id": plan["id"], "idempotency_key": "recover-apply", "approved": True,
        }).json()
        assert client.post(f"/api/agent/batch-jobs/{job['id']}/collect", json={}).status_code == 200
        apply_plan = client.post(f"/api/agent/batch-jobs/{job['id']}/apply/plan", json={}).json()
        environment["manager"].fail_next_registration = True
        with pytest.raises(OSError, match="simulated translation path registration failure"):
            client.post(f"/api/agent/batch-jobs/{job['id']}/apply", json={
                "apply_plan_id": apply_plan["id"], "approved": True,
            })
        archived_after_failure = environment["archive"].connection.execute(
            "SELECT COUNT(*) FROM translated_entries WHERE language_code='zh-TW'"
        ).fetchone()[0]
        assert archived_after_failure == 2
        assert environment["transport"].submissions and len(environment["transport"].submissions) == 1

    # New TestClient requests use newly constructed service/repository instances over the same durable files.
    with make_api_client(environment) as restarted_client:
        recovered = restarted_client.post(
            f"/api/agent/batch-jobs/{job['id']}/apply",
            json={"apply_plan_id": apply_plan["id"], "approved": True},
        )
        assert recovered.status_code == 200
        assert recovered.json()["apply_status"] == "applied"
    archived_after_recovery = environment["archive"].connection.execute(
        "SELECT COUNT(*) FROM translated_entries WHERE language_code='zh-TW'"
    ).fetchone()[0]
    assert archived_after_recovery == archived_after_failure == 2
    assert len(environment["transport"].submissions) == 1
    assert environment["manager"].registered_paths


@pytest.mark.asyncio
async def test_archive_compare_and_set_rejects_translation_changed_after_apply_plan(batch_environment):
    environment = batch_environment
    service = environment["service"]()
    plan = await service.plan(plan_request())
    job = await service.start(start_request(plan["id"], "archive-cas"))
    await service.collect(job["id"])
    snapshot = environment["artifacts"].get(plan["source_artifact"])
    version_id = ensure_source_version(environment["archive"], snapshot)
    environment["archive"].archive_translated_results(
        version_id,
        {"Game.csv": ["先前译文", "先前译文二"]},
        source_files(snapshot),
        "zh-TW",
    )
    apply_plan = await service.apply_plan(job["id"])
    environment["archive"].connection.execute(
        "UPDATE translated_entries SET translated_text=? WHERE source_entry_id=("
        "SELECT source_entry_id FROM source_entries WHERE version_id=? AND entry_key='1001') AND language_code='zh-TW'",
        ("第三方改动", version_id),
    )
    environment["archive"].connection.commit()

    with pytest.raises(BatchConflict) as caught:
        await environment["service"]().apply(job["id"], apply_plan["id"], approved=True)

    assert caught.value.code == "archive_revision_conflict"
    changed = environment["archive"].connection.execute(
        "SELECT translated_text FROM translated_entries t JOIN source_entries s "
        "ON s.source_entry_id=t.source_entry_id WHERE s.entry_key='1001' AND t.language_code='zh-TW'"
    ).fetchone()[0]
    assert changed == "第三方改动"


@pytest.mark.asyncio
async def test_output_integrity_is_checked_during_apply_recovery(batch_environment):
    environment = batch_environment
    service = environment["service"]()
    plan = await service.plan(plan_request())
    job = await service.start(start_request(plan["id"], "tamper-output"))
    await service.collect(job["id"])
    apply_plan = await service.apply_plan(job["id"])
    environment["manager"].fail_next_registration = True
    with pytest.raises(OSError):
        await service.apply(job["id"], apply_plan["id"], approved=True)

    output_file = Path(apply_plan["final_parent"]) / "zh-TW" / "Game.csv"
    output_file.write_text(output_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with make_api_client(environment) as client:
        rejected = client.post(f"/api/agent/batch-jobs/{job['id']}/apply", json={
            "apply_plan_id": apply_plan["id"], "approved": True,
        })
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "output_integrity_conflict"


@pytest.mark.parametrize("failure", ["malformed_custom_id_list", "duplicate_json_key", "unknown_custom_id"])
def test_collector_rejects_malformed_or_foreign_custom_ids_without_applying_results(failure):
    snapshot = {
        "game_id": "surviving_mars",
        "adapter_id": "surviving_mars_csv",
        "source_locale": "en",
        "files": [{"file_id": "source-1", "selected": True, "entries": [{
            "id": "entry-1", "key": "1001", "source": "Concrete source",
        }]}],
    }
    requests = [{"custom_id": "expected:0", "entry_ids": ["entry-1"]}]
    content = '{"translations":{"entry-1":"火星译文"}}'
    expected_result = {
        "custom_id": "expected:0",
        "response": {"status_code": 200, "body": {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}},
    }
    if failure == "malformed_custom_id_list":
        rows = [{**expected_result, "custom_id": ["expected:0"]}]
    elif failure == "duplicate_json_key":
        rows = [{**expected_result, "response": {"status_code": 200, "body": {
            "choices": [{"finish_reason": "stop", "message": {"content": '{"translations":{"entry-1":"甲","entry-1":"乙"}}'}}]
        }}}]
    else:
        rows = [expected_result, {"custom_id": "foreign:9", "error": {"code": "foreign"}}]

    collection = collect_results(snapshot, requests, {"results": rows}, "zh-TW")

    assert collection["translations"] == {}
    assert collection["complete_file_ids"] == []
    if failure == "duplicate_json_key":
        assert "parser_failure" in {item["code"] for item in collection["diagnostics"]}
    else:
        assert "unknown_custom_id" in {item["code"] for item in collection["diagnostics"]}


def test_batch_project_guard_persists_task_and_releases_real_remis_lock(tmp_path):
    main_db = tmp_path / "remis-main.sqlite3"
    assert migrate_main_database(str(main_db))
    repository = TaskRepository(str(main_db))
    guard = BatchProjectGuard(repository)

    with guard("project-guarded"):
        lock = repository.get_project_lock("project-guarded")
        assert lock is not None
        task = repository.get_task(lock["task_id"])
        assert task["kind"] == "translation"
        assert task["status"] == "running"
        assert task["agent_job_kind"] == "batch_apply"

    completed = repository.get_task(lock["task_id"])
    assert completed["status"] == "completed"
    assert repository.get_project_lock("project-guarded") is None


class ParadoxTokenTransport(FakeTransport):
    async def submit(self, payload):
        self.submissions.append(payload)
        request = payload["requests"][0]
        context = json.loads(request["body"]["messages"][1]["content"])
        translated = {
            entry["id"]: "使用 $KEY$ 指代 [GetName] 和 §Y重点§!。"
            for entry in context["entries"]
        }
        remote_id = "remote-paradox"
        self.remote_batches[remote_id] = {
            "id": remote_id,
            "status": "completed",
            "results": [{
                "custom_id": request["custom_id"],
                "response": {"status_code": 200, "body": {"choices": [{
                    "finish_reason": "stop", "message": {"content": json.dumps({"translations": translated}, ensure_ascii=False)}
                }]}},
            }],
        }
        return {"id": remote_id, "status": "queued"}


@pytest.mark.asyncio
async def test_real_project_manager_registers_and_rediscovers_new_mars_csv(
    tmp_path, real_project_manager, batch_environment,
):
    source_root = tmp_path / "mars-source"
    source_root.mkdir()
    source_file = source_root / "Game.csv"
    source_file.write_text(
        "ID,Text,Translation,VoiceActor,Context\n"
        "1001,Concrete source,,voice-a,context-a\n",
        encoding="utf-8",
        newline="",
    )
    created = await real_project_manager.create_project(
        name="Real project manager Mars fixture",
        folder_path=str(source_root),
        game_id="surviving_mars",
        source_language="en",
        import_mode="reference",
    )
    project_id = created["project_id"]
    source_manifest = await real_project_manager.get_project_files(project_id)
    source_rows = [item for item in source_manifest if item["file_type"] == "source"]
    assert [Path(item["file_path"]).name for item in source_rows] == ["Game.csv"]

    service = batch_environment["service"](
        project_manager=real_project_manager,
        custom_output_root=tmp_path / "real-manager-outputs",
    )
    plan = await service.plan(plan_request(project_id=project_id, file_ids=[source_rows[0]["file_id"]]))
    job = await service.start(start_request(plan["id"], "real-manager-mars"))
    await service.collect(job["id"])
    apply_plan = await service.apply_plan(job["id"])
    result = await service.apply(job["id"], apply_plan["id"], approved=True)

    output_file = Path(result["output_paths"][0]) / "Game.csv"
    assert output_file.is_file()
    current = await real_project_manager.get_project_files(project_id)
    translations = [item for item in current if item["file_type"] == "translation"]
    assert any(Path(item["file_path"]).resolve() == output_file.resolve() for item in translations)
    from scripts.core.project_json_manager import ProjectJsonManager
    registered_dirs = ProjectJsonManager(source_root).get_config()["translation_dirs"]
    assert str(output_file.parent) in registered_dirs


@pytest.mark.asyncio
async def test_real_project_manager_renders_paradox_tokens_to_simp_chinese_slot_and_archives_zh_tw(
    tmp_path, real_project_manager, batch_environment,
):
    from scripts.core.game_adapters.registry import get_adapter
    from scripts.utils.game_format_contract import format_structure_signature

    source_root = tmp_path / "vic3-source"
    source_file = source_root / "localisation" / "english" / "demo_l_english.yml"
    source_file.parent.mkdir(parents=True)
    source_text = 'l_english:\n demo.token:0 "Use $KEY$ for [GetName] and §Yhighlight§!."\n'
    source_file.write_text(source_text, encoding="utf-8", newline="")
    created = await real_project_manager.create_project(
        name="Real project manager Paradox fixture",
        folder_path=str(source_root),
        game_id="victoria3",
        source_language="en",
        import_mode="reference",
    )
    project_id = created["project_id"]
    source_manifest = await real_project_manager.get_project_files(project_id)
    source_rows = [item for item in source_manifest if item["file_type"] == "source"]
    assert len(source_rows) == 1

    transport = ParadoxTokenTransport()
    service = batch_environment["service"](
        wire=transport,
        project_manager=real_project_manager,
        custom_output_root=tmp_path / "real-manager-vic3-outputs",
    )
    plan = await service.plan(plan_request(project_id=project_id, file_ids=[source_rows[0]["file_id"]]))
    job = await service.start(start_request(plan["id"], "real-manager-paradox"))
    collected = await service.collect(job["id"])
    assert collected["collection"]["failed_custom_ids"] == []
    apply_plan = await service.apply_plan(job["id"])
    result = await service.apply(job["id"], apply_plan["id"], approved=True)

    output_root = Path(result["output_paths"][0])
    output_file = output_root / "localisation" / "simp_chinese" / "demo_l_simp_chinese.yml"
    assert output_file.is_file()
    rendered = output_file.read_text(encoding="utf-8")
    assert rendered.startswith("l_simp_chinese:")
    adapter = get_adapter({"id": "victoria3"})
    source_document = adapter.parse(source_file)
    target_document = adapter.parse(output_file)
    source_entry = source_document.entries[0].value
    target_entry = target_document.entries[0].value
    assert format_structure_signature(source_entry, "victoria3") == format_structure_signature(target_entry, "victoria3")
    assert "$KEY$" in target_entry and "[GetName]" in target_entry
    assert "§Y" in target_entry and "§!" in target_entry
    archive_rows = batch_environment["archive"].connection.execute(
        "SELECT t.language_code,t.translated_text FROM translated_entries t "
        "JOIN source_entries s ON s.source_entry_id=t.source_entry_id ORDER BY s.entry_key"
    ).fetchall()
    assert len(archive_rows) == 1
    assert archive_rows[0]["language_code"] == "zh-TW"
    assert archive_rows[0]["translated_text"] == target_entry
    registered = await real_project_manager.get_project_files(project_id)
    assert any(Path(item["file_path"]).resolve() == output_file.resolve() and item["file_type"] == "translation"
               for item in registered)
