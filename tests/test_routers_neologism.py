from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from scripts.routers import neologism
from scripts.schemas.neologism import ApproveNeologismRequest
from scripts.schemas.neologism import MineNeologismsRequest


def test_approval_requires_translation_unless_reusing_duplicate():
    with pytest.raises(ValidationError, match="final_translation"):
        ApproveNeologismRequest(project_id="project-1")

    payload = ApproveNeologismRequest(
        project_id="project-1",
        resolution="duplicate",
        final_translation="",
    )
    assert payload.final_translation == ""


def test_full_archive_task_identity_does_not_reuse_neologism_copy():
    payload = MineNeologismsRequest(
        project_id="project-1",
        api_provider="openrouter",
        analysis_scope="narrative_context",
    )

    kind, title = neologism._mining_task_identity(payload, {"name": "Horizon Signal"})

    assert kind == "context_archive_analysis"
    assert title == "Build project archive for Horizon Signal"


@pytest.mark.asyncio
async def test_selected_mining_files_must_be_indexed_and_inside_project(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    allowed_file = source_root / "localisation.yml"
    allowed_file.write_text('l_english:\n key:0 "Pax Remisia"\n', encoding="utf-8")
    untracked_file = source_root / "untracked.yml"
    untracked_file.write_text('l_english:\n key:0 "Hidden"\n', encoding="utf-8")
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("secret", encoding="utf-8")

    async def get_project_files(project_id):
        assert project_id == "project-1"
        return [{"file_path": str(allowed_file)}]

    monkeypatch.setattr(neologism.project_manager, "get_project_files", get_project_files)
    project = {"project_id": "project-1", "source_path": str(source_root)}

    assert await neologism._resolve_project_mining_files(project, [str(allowed_file)]) == [str(allowed_file.resolve())]

    with pytest.raises(HTTPException, match="inside the project source"):
        await neologism._resolve_project_mining_files(project, [str(outside_file)])
    with pytest.raises(HTTPException, match="not indexed"):
        await neologism._resolve_project_mining_files(project, [str(untracked_file)])


@pytest.mark.asyncio
async def test_auto_selection_uses_only_supported_indexed_files(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    supported = source_root / "events.yml"
    supported.write_text('l_english:\n key:0 "Curia Caelestis"\n', encoding="utf-8")
    unsupported = source_root / "thumbnail.png"
    unsupported.write_bytes(b"png")
    project_metadata = source_root / ".remis_project.json"
    project_metadata.write_text('{"name":"not localization"}', encoding="utf-8")

    async def get_project_files(_project_id):
        return [
            {"file_path": str(supported)},
            {"file_path": str(unsupported)},
            {"file_path": str(project_metadata)},
        ]

    monkeypatch.setattr(neologism.project_manager, "get_project_files", get_project_files)

    files = await neologism._resolve_project_mining_files(
        {"project_id": "project-1", "source_path": str(source_root)},
        None,
    )

    assert files == [str(supported.resolve())]


@pytest.mark.asyncio
async def test_list_mining_files_returns_only_eligible_source_files(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    events = source_root / "events.yml"
    events.write_text('l_english:\n key:0 "Pax Remisia"\n', encoding="utf-8")

    async def get_project(project_id):
        return {"project_id": project_id, "source_path": str(source_root)}

    async def get_project_files(_project_id):
        return [{"file_path": str(events), "relative_path": "events.yml"}]

    monkeypatch.setattr(neologism.project_manager, "get_project", get_project)
    monkeypatch.setattr(neologism.project_manager, "get_project_files", get_project_files)

    result = await neologism.list_mining_files("project-1")

    assert result == [{"file_path": str(events.resolve()), "relative_path": "events.yml"}]


@pytest.mark.asyncio
async def test_processed_view_and_restore_preserve_written_glossary_entries(monkeypatch):
    async def get_project(project_id):
        return {"project_id": project_id}

    monkeypatch.setattr(neologism.project_manager, "get_project", get_project)
    monkeypatch.setattr(
        neologism.neologism_manager,
        "get_candidates",
        lambda project_id, view: [{
            "id": "candidate-1",
            "status": "approved",
            "project_id": project_id,
            "view": view,
        }],
    )
    monkeypatch.setattr(
        neologism.neologism_manager,
        "restore_candidate",
        lambda project_id, candidate_id: "approved",
    )

    processed = await neologism.list_neologisms("project-1", view="processed")
    restored = await neologism.restore_neologism(
        "candidate-1",
        neologism.RestoreNeologismRequest(project_id="project-1"),
    )

    assert processed[0]["view"] == "processed"
    assert restored == {
        "status": "success",
        "previous_status": "approved",
        "glossary_entry_preserved": True,
    }


@pytest.mark.asyncio
async def test_reject_conflicts_with_an_existing_terminal_verdict(monkeypatch):
    async def get_project(project_id):
        return {"project_id": project_id}

    monkeypatch.setattr(neologism.project_manager, "get_project", get_project)
    monkeypatch.setattr(
        neologism.neologism_manager,
        "reject_candidate",
        lambda project_id, candidate_id: "approved",
    )

    with pytest.raises(HTTPException) as exc_info:
        await neologism.reject_neologism("candidate-1", {"project_id": "project-1"})

    assert exc_info.value.status_code == 409
    assert "already approved" in exc_info.value.detail
