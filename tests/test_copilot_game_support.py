from __future__ import annotations

import pytest

from scripts.app_settings import GAME_PROFILES_BY_ID
from scripts.core.copilot import game_support, read_tools
from scripts.core.copilot import workflow
from scripts.core.copilot import help_agent
from scripts.core.copilot.help_agent import (
    HelpDeps,
    _project_is_in_inspected_catalog,
    requests_incremental_workflow,
)
from scripts.core.copilot.help_pack import AGENT_OPS_SUMMARY, HELP_SKILLS, read_help_skills


def test_static_support_is_allowlisted_and_states_three_game_boundaries():
    pz = game_support.read_game_support("project_zomboid")
    rimworld = game_support.read_game_support("rimworld")
    mars = game_support.read_game_support("surviving_mars")

    assert pz["output_kind"] == "independent_translation_mod"
    assert rimworld["output_kind"] == "independent_translation_mod"
    assert pz["incremental_policy"] and rimworld["incremental_policy"]
    assert pz["runtime_verified"] is False
    assert rimworld["runtime_verified"] is False
    assert "ModItemLocTable CSV" in mars["formats"]
    assert mars["output_kind"] == "csv_files"
    assert mars["capabilities"]["independent_translation_mod"] is True
    assert mars["translation_package"]["supported"] is True
    assert mars["translation_package"]["output_kind"] == "independent_translation_mod"
    assert mars["translation_package"]["export_mode"] == "manual_install"
    assert "translation-package/plan" in mars["translation_package"]["plan_endpoint"]
    assert "CSV" in AGENT_OPS_SUMMARY
    assert "游戏内验收" in AGENT_OPS_SUMMARY


def test_support_help_skill_is_registered_for_bundled_guide():
    assert HELP_SKILLS["multi_game_localization"]["resources"] == (
        "zh/user-guides/multi-game-localization.md",
    )
    excerpts = read_help_skills(["multi_game_localization"])
    assert excerpts and "Project Zomboid" in excerpts[0]["content"]


def test_help_copilot_requires_project_from_inspected_catalog():
    deps = HelpDeps(workflow_entities={"projects": [{"project_id": "project-1"}]})
    assert not _project_is_in_inspected_catalog(deps, "project-1")
    deps.inspected_workflow_entities = True
    assert _project_is_in_inspected_catalog(deps, "project-1")
    assert not _project_is_in_inspected_catalog(deps, "another-project")


def test_help_agent_does_not_claim_incremental_workflow_execution():
    assert requests_incremental_workflow([{"role": "user", "content": "请做增量翻译"}])
    assert requests_incremental_workflow([{"role": "user", "content": "translate only new entries"}])
    assert not requests_incremental_workflow([{"role": "user", "content": "How do I configure RimWorld?"}])


@pytest.mark.asyncio
async def test_registered_project_support_tool_calls_service_with_version(monkeypatch):
    class CapturingAgent:
        def __init__(self, _model, **_kwargs):
            self._function_toolset = type("ToolSet", (), {"tools": {}})()

        def tool(self, function):
            self._function_toolset.tools[function.__name__] = function
            return function

        def output_validator(self, function):
            return function

    async def fake_service(project_id, game_version):
        assert (project_id, game_version) == ("catalogued-project", "1.6.1")
        return {"project_id": project_id, "requested_game_version": game_version, "read_only": True}

    monkeypatch.setattr(help_agent, "Agent", CapturingAgent)
    monkeypatch.setattr(help_agent, "build_help_model", lambda *args, **kwargs: (object(), {}, None))
    monkeypatch.setattr(help_agent, "_inspect_project_game_support", fake_service)
    agent = help_agent.build_help_agent("offline-test")
    deps = HelpDeps(
        inspected_workflow_entities=True,
        workflow_entities={"projects": [{"project_id": "catalogued-project"}]},
    )
    tool = agent._function_toolset.tools["inspect_project_game_support"]

    result = await tool(
        type("Context", (), {"deps": deps})(),
        project_id="catalogued-project",
        game_version="1.6.1",
    )

    assert result["requested_game_version"] == "1.6.1"
    assert deps.game_support_results["catalogued-project"] == result


def test_game_support_read_tool_schemas_are_read_only_and_bound():
    schemas = {schema["name"]: schema for schema in read_tools.build_workflow_read_tool_schemas()}

    assert list(schemas["inspect_project_game_support"]["parameters"]["properties"]) == [
        "game_version"
    ]
    game_ids = schemas["get_game_support"]["parameters"]["properties"]["game_id"]["enum"]
    assert game_ids == list(GAME_PROFILES_BY_ID)
    assert {"project_zomboid", "rimworld", "surviving_mars", "stellaris"}.issubset(game_ids)


def test_plan_summary_only_reports_counts_for_recognized_resource_coverage():
    structured = workflow._localization_plan_summary({
        "coverage_scope": "recognized_resources_only",
        "recognized_resource_count": 2,
        "recognized_entry_count": 15,
    })
    paradox = workflow._localization_plan_summary({
        "coverage_scope": "use_existing_file_inspection",
        "recognized_resource_count": 0,
        "recognized_entry_count": 0,
    })

    assert "已识别 2 个资源、15 个条目" in structured
    assert "已识别" not in paradox


@pytest.mark.asyncio
async def test_project_support_tool_strips_absolute_paths(monkeypatch):
    async def fake_inspect(project_id, game_version=None):
        assert project_id == "server-bound"
        assert game_version == "1.6.1"
        return {
            "project_id": project_id,
            "game_id": "rimworld",
            "support": game_support.read_game_support("rimworld"),
            "resources": [{"path": "C:/private/mod/Languages/English/Keyed/a.xml", "entry_count": 3}],
            "diagnostics": [{"code": "unsupported", "message": "Review C:/private/mod/Defs/a.xml", "path": "C:/private/mod/Defs/a.xml", "severity": "warning"}],
            "recognized_resource_count": 1,
            "recognized_entry_count": 3,
            "coverage_scope": "recognized_resources_only",
            "has_blocking_diagnostics": False,
            "runtime_verified": False,
            "allowed_actions": ["create_translation_plan"],
        }

    monkeypatch.setattr(game_support, "_inspect_project_game_support", fake_inspect)
    result = await game_support.inspect_project_game_support("server-bound", "1.6.1")

    assert result["resources"] == [{"path": "a.xml", "entry_count": 3}]
    assert result["diagnostics"][0]["path"] == "a.xml"
    assert "C:/private" not in result["diagnostics"][0]["message"]
    assert "C:/private" not in str(result)
    assert result["coverage_scope"] == "recognized_resources_only"
    assert result["runtime_verified"] is False


@pytest.mark.asyncio
async def test_workflow_read_tool_uses_bound_project_id(monkeypatch):
    seen = []

    async def fake_inspect(project_id, game_version=None):
        seen.append(project_id)
        assert game_version == "42.1"
        return {"project_id": project_id, "resources": [], "diagnostics": []}

    monkeypatch.setattr(read_tools, "inspect_project_game_support", fake_inspect)
    result = await read_tools.execute_workflow_read_tool(
        "inspect_project_game_support", {"project_id": "attacker-choice", "game_version": "42.1"},
        project_id="approved-project", target_lang_codes=["zh-CN"],
    )

    assert seen == ["approved-project"]
    assert result["project_id"] == "approved-project"
