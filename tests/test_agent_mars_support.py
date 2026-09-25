"""Read-only Surviving Mars support discovery and Agent boundaries."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.core import surviving_mars_csv
from scripts.core.services import game_support_service, mars_game_support
from scripts.core.services.agent_translation_plan_service import (
    AgentTranslationPlanError,
    _game_plan_support,
)
from scripts.routers import agent as agent_router
from scripts.schemas.agent import AgentJobPlanRequest


def _write(path: Path, content: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="")
    return path


def _csv(rows: str = "") -> str:
    return ",".join(surviving_mars_csv.HEADER) + "\r\n" + rows


def _request(source: Path, *, dry_run: bool = False) -> AgentJobPlanRequest:
    return AgentJobPlanRequest(
        project_id="mars-project", api_provider="lm_studio", model="no-call-fixture",
        translation_context_mode="none", dry_run=dry_run,
    )


def _plan(source: Path) -> dict:
    return {"inspection": {"game_id": "surviving_mars", "source_path": str(source),
                            "source_language": "en"}}


def test_csv_support_preserves_source_bytes_leading_zero_ids_and_multiline_rows(tmp_path: Path):
    root = tmp_path / "editable-mod"
    first = _write(root / "Loc/Game.csv", (
        "\ufeff" + _csv('000123,"First line\r\nsecond line",,"Voice A","Context, one"\r\n'
                        '000124,"A ""quoted"" value",,"Voice B","Context two"\r\n')
    ).encode("utf-8"))
    second = _write(root / "Loc/Other.csv", _csv('000007,Another row,,,\r\n').encode("utf-8"))
    unrelated = _write(root / "Loc/NotATable.csv", b"key,value\r\na,b\r\n")
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (first, second, unrelated)}

    result = mars_game_support.inspect_csv_support(str(root))

    assert [Path(item["path"]).name for item in result["resources"]] == ["Game.csv", "Other.csv"]
    assert [item["entry_count"] for item in result["resources"]] == [2, 1]
    parsed = surviving_mars_csv.parse_file(first)
    assert [entry.key for entry in parsed.entries] == ["000123", "000124"]
    assert parsed.entries[0].value == "First line\r\nsecond line"
    assert not result["diagnostics"]
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (first, second, unrelated)} == before


def test_ordinary_csv_is_ignored_instead_of_counted_as_game_resource(tmp_path: Path):
    root = tmp_path / "ordinary-only"
    _write(root / "data.csv", "id,text\n001,ordinary\n")

    result = mars_game_support.inspect_csv_support(str(root))

    assert result["resources"] == []
    assert [item["code"] for item in result["diagnostics"]] == ["csv_resources_missing"]
    assert result["diagnostics"][0]["severity"] == "error"


def test_duplicate_id_table_is_reported_as_parse_diagnostic(tmp_path: Path):
    root = tmp_path / "duplicate"
    _write(root / "Game.csv", _csv("001,First,,,\n001,Duplicate,,,\n"))

    result = mars_game_support.inspect_csv_support(str(root))

    assert result["resources"] == []
    assert result["diagnostics"][0]["code"] == "resource_parse_error"
    assert "Duplicate ID" in result["diagnostics"][0]["message"]
    assert any(item["code"] == "csv_resources_missing" for item in result["diagnostics"])


def test_compiled_package_only_blocks_but_csv_with_fpk_is_warning(tmp_path: Path):
    only_fpk = tmp_path / "fpk-only"
    _write(only_fpk / "ModContent.fpk", b"synthetic compiled fixture")
    blocked = mars_game_support.inspect_csv_support(str(only_fpk))
    assert any(item["code"] == "compiled_package_unsupported" and item["severity"] == "error"
               for item in blocked["diagnostics"])

    editable = tmp_path / "fpk-with-csv"
    _write(editable / "ModContent.fpk", b"synthetic compiled fixture")
    _write(editable / "Game.csv", _csv("001,Text,,,\n"))
    supported = mars_game_support.inspect_csv_support(str(editable))
    assert len(supported["resources"]) == 1
    warning = next(item for item in supported["diagnostics"]
                   if item["code"] == "compiled_package_unsupported")
    assert warning["severity"] == "warning"


def test_missing_directory_returns_blocking_diagnostics(tmp_path: Path):
    result = mars_game_support.inspect_csv_support(str(tmp_path / "not-created"))

    assert result["resources"] == []
    assert result["metadata"]["scan_complete"] is False
    assert any(item["code"] == "resource_discovery_error" and item["severity"] == "error"
               for item in result["diagnostics"])
    assert any(item["code"] == "csv_resources_missing" for item in result["diagnostics"])


def test_scan_limit_marks_partial_csv_discovery_incomplete_and_blocking(tmp_path: Path, monkeypatch):
    root = tmp_path / "limited-source"
    _write(root / "a.csv", _csv("001,First,,,\n"))
    _write(root / "b.csv", _csv("002,Second,,,\n"))
    monkeypatch.setattr(mars_game_support, "MAX_SCAN_FILES", 1)

    result = mars_game_support.inspect_csv_support(str(root))

    assert result["resources"]
    assert result["metadata"]["scan_complete"] is False
    assert any(item["severity"] == "error" and "scan limit" in item["message"]
               for item in result["diagnostics"])


def test_directory_symlink_is_not_traversed_when_platform_allows(tmp_path: Path):
    root = tmp_path / "source"
    root.mkdir()
    external = tmp_path / "outside"
    _write(external / "Game.csv", _csv("001,Secret,,,\n"))
    try:
        os.symlink(external, root / "linked", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Directory symlink is unavailable: {exc}")

    result = mars_game_support.inspect_csv_support(str(root))

    assert result["resources"] == []
    assert any(item["code"] == "csv_resources_missing" for item in result["diagnostics"])


def test_real_agent_inspect_routes_expose_mars_scan_read_only(client, tmp_path, monkeypatch):
    from scripts.shared import services

    source = tmp_path / "mars-source"
    table = _write(source / "Game.csv", _csv("000001,Surface,,,\n"))
    source_bytes = table.read_bytes()
    project = {"project_id": "mars-route-project", "name": "Mars fixture",
               "game_id": "surviving_mars", "source_language": "en",
               "source_path": str(source), "status": "active"}

    async def get_project(_project_id):
        return project

    monkeypatch.setattr(agent_router.project_manager, "get_project", get_project)
    monkeypatch.setattr(services.project_manager, "get_project", get_project)
    monkeypatch.setattr(agent_router, "_validate_agent_import_path", lambda path: {
        "folder_path": str(source), "localization_file_count": 0,
    })
    inspect = client.post("/api/agent/projects/inspect", json={
        "folder_path": str(source), "game_id": "surviving_mars", "source_language": "en",
    })
    assert inspect.status_code == 200, inspect.text
    scan = inspect.json()["inspection"]["game_support"]
    assert scan["recognized_resource_count"] == 1
    assert scan["recognized_entry_count"] == 1
    assert scan["runtime_verified"] is False
    get_scan = client.get(f"/api/agent/projects/{project['project_id']}/game-support")
    assert get_scan.status_code == 200, get_scan.text
    assert get_scan.json()["recognized_resource_count"] == 1
    assert table.read_bytes() == source_bytes


def test_plan_blocks_invalid_csv_but_dry_run_retains_diagnostics(tmp_path: Path):
    invalid_source = tmp_path / "invalid-mod"
    _write(invalid_source / "Game.csv", _csv("001,First,,,\n001,Duplicate,,,\n"))

    with pytest.raises(AgentTranslationPlanError) as caught:
        _game_plan_support(_request(invalid_source), _plan(invalid_source))
    assert (caught.value.status_code, caught.value.code) == (409, "game_resources_blocked")
    assert caught.value.details["game_support"]["has_blocking_diagnostics"] is True

    dry_support = _game_plan_support(
        _request(invalid_source, dry_run=True), _plan(invalid_source),
    )
    assert dry_support["has_blocking_diagnostics"] is True
    assert any(item["code"] == "resource_parse_error" for item in dry_support["diagnostics"])


def test_copilot_workflow_blocks_fpk_only_source_before_creating_plan(tmp_path: Path, monkeypatch):
    from scripts.core.copilot import workflow

    root = tmp_path / "compiled-only"
    _write(root / "ModContent.fpk", b"synthetic compiled package")
    monkeypatch.setattr(workflow, "inspect_mod_folder", lambda path: {"folder_path": str(path)})

    with pytest.raises(ValueError, match="Resolve Surviving Mars CSV diagnostics"):
        workflow.create_localization_plan(
            folder_path=str(root), project_name="Mars FPK fixture", game_id="surviving_mars",
            source_language="en", import_mode="copy", target_language="zh-CN",
            api_provider="lm_studio", model="no-provider-call-fixture",
        )


def test_copilot_reads_mars_csv_contract_and_dedicated_help_guide():
    from scripts.core.copilot import game_support as copilot_game_support
    from scripts.core.copilot import help_pack

    support = copilot_game_support.read_game_support("surviving_mars")
    assert support["csv_contract"]["header"] == list(surviving_mars_csv.HEADER)
    assert support["csv_contract"]["id_policy"].startswith("ASCII decimal")
    assert support["csv_contract"]["compressed_packages_supported"] is False
    assert support["runtime_verified"] is False

    help_pack._read_allowlisted_doc.cache_clear()
    guides = help_pack.read_help_skills(["surviving_mars"])
    assert guides
    assert guides[0]["path"] == "zh/user-guides/surviving-mars.md"
    assert "ModItemLocTable" in guides[0]["content"]
    assert "ModContent.fpk" in guides[0]["content"]


@pytest.fixture
def client():
    from scripts.web_server import app
    with TestClient(app) as test_client:
        yield test_client
