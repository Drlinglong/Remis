"""Plan guards use real game-resource discovery and do not invoke providers."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.core.services.agent_translation_plan_service import (
    AgentTranslationPlanError,
    _game_plan_support,
)
from scripts.schemas.agent import AgentJobPlanRequest


SHELL = {"name": "Italian", "code": "custom", "key": "l_english", "folder_prefix": "it-"}


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _source(root: Path, game_id: str, shape: str) -> Path:
    if game_id == "project_zomboid":
        _write(root / "mod.info", "id=plan.fixture\nname=Plan fixture\n")
        if shape == "blocked":
            _write(root / "media/lua/shared/Translate/EN/UI.json", '{"UI_Title":')
        elif shape == "valid":
            _write(root / "media/lua/shared/Translate/EN/UI.json", '{"UI_Title":"Open %1"}')
    else:
        _write(root / "About/About.xml", "<ModMetaData><packageId>plan.fixture</packageId></ModMetaData>")
        if shape == "blocked":
            _write(root / "Languages/English/Keyed/UI.xml", "<LanguageData><Title>")
        elif shape == "valid":
            _write(root / "Languages/English/Keyed/UI.xml", "<LanguageData><Title>Open {0}</Title></LanguageData>")
    return root


def _request(game_id: str, *, workflow: str = "initial", dry_run: bool = False,
             use_resume: bool = False, shell: bool = False) -> AgentJobPlanRequest:
    values = {
        "project_id": "plan-fixture-project",
        "workflow": workflow,
        "api_provider": "lm_studio",
        "model": "no-provider-call-fixture",
        "translation_context_mode": "none",
        "dry_run": dry_run,
        "use_resume": use_resume,
    }
    if shell:
        values.update(target_lang_codes=["custom"], custom_lang_config=SHELL)
    return AgentJobPlanRequest(**values)


def _plan(game_id: str, source: Path | None = None) -> dict:
    inspection = {"game_id": game_id}
    if source is not None:
        inspection.update(source_path=str(source), source_language="en")
    return {"inspection": inspection}


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld"])
@pytest.mark.parametrize("shape", ["empty", "blocked"])
def test_non_dry_run_blocks_unrecognized_or_parse_blocked_game_resources(
    tmp_path: Path, game_id: str, shape: str,
):
    source = _source(tmp_path / game_id, game_id, shape)

    with pytest.raises(AgentTranslationPlanError) as caught:
        _game_plan_support(_request(game_id), _plan(game_id, source))

    assert (caught.value.status_code, caught.value.code) == (409, "game_resources_blocked")
    support = caught.value.details["game_support"]
    if shape == "empty":
        assert support["recognized_resource_count"] == 0
    else:
        assert support["has_blocking_diagnostics"] is True


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld"])
@pytest.mark.parametrize("shape", ["empty", "blocked"])
def test_dry_run_returns_resource_diagnostics_without_blocking(
    tmp_path: Path, game_id: str, shape: str,
):
    source = _source(tmp_path / game_id, game_id, shape)

    support = _game_plan_support(_request(game_id, dry_run=True), _plan(game_id, source))

    assert support["read_only"] is True
    if shape == "empty":
        assert support["recognized_resource_count"] == 0
    else:
        assert support["has_blocking_diagnostics"] is True
        assert support["diagnostics"]


def test_incremental_checkpoint_resume_is_rejected_before_resource_plan():
    with pytest.raises(AgentTranslationPlanError) as caught:
        _game_plan_support(
            _request("project_zomboid", workflow="incremental", use_resume=True),
            _plan("project_zomboid"),
        )

    assert (caught.value.status_code, caught.value.code) == (
        409, "incremental_resume_unsupported",
    )


@pytest.mark.parametrize("game_id", ["project_zomboid", "rimworld", "surviving_mars"])
def test_non_paradox_games_reject_paradox_shell_languages(game_id: str):
    with pytest.raises(AgentTranslationPlanError) as caught:
        _game_plan_support(_request(game_id, shell=True), _plan(game_id))

    assert (caught.value.status_code, caught.value.code) == (400, "unsupported_shell_language")


def test_paradox_initial_shell_is_preserved_and_incremental_shell_is_rejected():
    initial = _game_plan_support(_request("victoria3", shell=True), _plan("victoria3"))
    assert initial["output_kind"] == "paradox_mod"

    with pytest.raises(AgentTranslationPlanError) as caught:
        _game_plan_support(
            _request("victoria3", workflow="incremental", shell=True), _plan("victoria3"),
        )

    assert (caught.value.status_code, caught.value.code) == (400, "unsupported_shell_language")


def test_game_version_from_project_plan_is_used_for_resource_approval(monkeypatch, tmp_path):
    from scripts.core.services import game_support_service

    source = tmp_path / "versioned-project"
    source.mkdir()
    captured = []

    def inspect(game_id, source_path, source_language, game_version=None):
        captured.append((game_id, source_path, source_language, game_version))
        return {
            "output_kind": "independent_translation_mod",
            "read_only": True,
            "has_blocking_diagnostics": False,
            "recognized_resource_count": 1,
        }

    monkeypatch.setattr(game_support_service, "inspect_game_support", inspect)
    result = _game_plan_support(
        _request("rimworld"),
        {"inspection": {
            "game_id": "rimworld", "source_path": str(source),
            "source_language": "en", "game_version": "1.6.4512",
        }},
    )

    assert captured == [("rimworld", str(source), "en", "1.6.4512")]
    assert result["recognized_resource_count"] == 1
