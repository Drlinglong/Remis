from pathlib import Path

import pytest

from scripts.core.copilot import workflow
from scripts.core.copilot import agent_planner, read_tools


def _make_mod(tmp_path: Path) -> Path:
    mod = tmp_path / "Example Mod"
    loc = mod / "localisation" / "english"
    loc.mkdir(parents=True)
    (loc / "example_l_english.yml").write_text("l_english:\n key: value\n", encoding="utf-8")
    (mod / "descriptor.mod").write_text('name="Example"\n', encoding="utf-8")
    return mod


def test_inspection_is_read_only_and_scoped_to_selected_folder(tmp_path):
    mod = _make_mod(tmp_path)
    before = sorted(path.relative_to(mod).as_posix() for path in mod.rglob("*"))
    result = workflow.inspect_mod_folder(str(mod))
    after = sorted(path.relative_to(mod).as_posix() for path in mod.rglob("*"))

    assert result["read_only"] is True
    assert result["localization_file_count"] == 1
    assert result["metadata_files"] == ["descriptor.mod"]
    assert before == after


def test_async_read_tools_do_not_use_blocking_requests():
    source = Path(read_tools.__file__).read_text(encoding="utf-8")
    assert "requests.get" not in source
    assert "httpx.AsyncClient" in source
    assert "asyncio.to_thread" in source


@pytest.mark.asyncio
async def test_plan_requires_approval_and_executes_exactly_once(tmp_path, monkeypatch):
    mod = _make_mod(tmp_path)
    calls = []

    async def fake_create_project(**kwargs):
        calls.append(kwargs)
        return {"project_id": "project-1", "name": kwargs["name"]}

    monkeypatch.setattr(workflow.project_manager, "create_project", fake_create_project)
    plan = workflow.create_localization_plan(
        folder_path=str(mod),
        project_name="Example CN",
        game_id="stellaris",
        source_language="en",
        import_mode="reference",
    )

    assert calls == []
    assert plan["status"] == "awaiting_approval"
    assert plan["requires_approval"] is True

    result = await workflow.approve_and_execute_plan(plan["plan_id"])
    assert result["status"] == "completed"
    assert calls == [plan["execution_args"]]
    assert result["next_action"]["action"] == "open_initial_translation"

    with pytest.raises(RuntimeError, match="already been executed"):
        await workflow.approve_and_execute_plan(plan["plan_id"])


def test_plan_rejects_missing_folder_without_writes(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        workflow.create_localization_plan(
            folder_path=str(tmp_path / "missing"),
            project_name="Missing",
            game_id="stellaris",
            source_language="en",
            import_mode="copy",
        )


@pytest.mark.asyncio
async def test_translation_plan_is_read_only_until_reserved(monkeypatch):
    async def fake_get_project(project_id):
        return {
            "project_id": project_id,
            "name": "Example CN",
            "source_path": "C:/mods/example",
            "source_language": "en",
        }

    async def fake_get_files(project_id):
        return [{"file_id": "a"}, {"file_id": "b"}]

    monkeypatch.setattr(workflow.project_manager, "get_project", fake_get_project)
    monkeypatch.setattr(workflow.project_manager, "get_project_files", fake_get_files)

    plan = await workflow.create_translation_plan(
        project_id="project-1",
        target_lang_codes=["zh-CN"],
        api_provider="lm_studio",
        model="google/gemma-4-31b-qat",
        batch_size_limit=10,
        concurrency_limit=1,
        rpm_limit=40,
    )

    assert plan["inspection"]["project_file_count"] == 2
    assert plan["status"] == "awaiting_approval"
    args = workflow.reserve_translation_plan(plan["plan_id"])
    assert args == plan["execution_args"]
    assert args["project_id"] == "project-1"
    assert args["embedded_workshop"]["follow_primary_settings"] is True
    with pytest.raises(RuntimeError, match="already been executed"):
        workflow.reserve_translation_plan(plan["plan_id"])


@pytest.mark.asyncio
async def test_translation_plan_rejects_source_as_target(monkeypatch):
    async def fake_get_project(project_id):
        return {"project_id": project_id, "name": "Example", "source_language": "en"}

    async def fake_get_files(project_id):
        return []

    monkeypatch.setattr(workflow.project_manager, "get_project", fake_get_project)
    monkeypatch.setattr(workflow.project_manager, "get_project_files", fake_get_files)
    with pytest.raises(ValueError, match="must differ"):
        await workflow.create_translation_plan(
            project_id="project-1",
            target_lang_codes=["en"],
            api_provider="lm_studio",
            model="local-model",
        )


@pytest.mark.asyncio
async def test_read_tools_bind_project_id_server_side(monkeypatch):
    async def fake_get_project(project_id):
        return {"project_id": project_id, "name": "Demo", "game_id": "victoria3", "source_language": "en", "source_path": "C:/demo"}

    async def fake_get_files(project_id):
        return [{"file_path": "localization/english/a.yml", "status": "todo", "original_key_count": 12, "line_count": 14}]

    monkeypatch.setattr(read_tools, "_snapshot_project", lambda project_id: {"project_id": project_id, "name": "Demo", "game_id": "victoria3", "source_language": "en", "source_path": "C:/demo"})
    monkeypatch.setattr(read_tools, "_snapshot_files", lambda project_id: [{"file_path": "localization/english/a.yml", "status": "todo", "original_key_count": 12, "line_count": 14}])
    result = await read_tools.execute_workflow_read_tool(
        "inspect_project", {"project_id": "attacker-choice"},
        project_id="approved-project", target_lang_codes=["zh-CN"],
    )
    assert result["project_id"] == "approved-project"
    assert result["read_only"] is True
    with pytest.raises(ValueError, match="not allowlisted"):
        await read_tools.execute_workflow_read_tool(
            "write_file", {}, project_id="approved-project", target_lang_codes=["zh-CN"]
        )


@pytest.mark.asyncio
async def test_agent_controls_read_tool_selection(monkeypatch):
    from types import SimpleNamespace
    from pydantic_ai.usage import RunUsage

    class FakeAgent:
        async def run(self, prompt, *, deps, usage_limits):
            deps.inspected_context = {"models": {"provider": "lm_studio", "models": ["local-model"]}}
            deps.tool_calls.append({"name": "inspect_translation_context", "arguments": {}})
            output = agent_planner.TranslationRecommendation(
                summary="small project", api_provider="lm_studio", model="local-model",
                batch_size_limit=10, concurrency_limit=1, rpm_limit=40,
            )
            return SimpleNamespace(output=output, usage=RunUsage())

    monkeypatch.setattr(agent_planner, "_build_agent", lambda **kwargs: FakeAgent())
    result = await agent_planner.recommend_initial_translation(
        project_id="project-1", target_lang_codes=["zh-CN"], preferred_provider="lm_studio"
    )
    assert result["tool_calls"][0] == {"name": "inspect_translation_context", "arguments": {}}
    assert result["recommendation"]["model"] == "local-model"
    assert result["read_only"] is True
