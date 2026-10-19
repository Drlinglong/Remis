"""Workshop-folder discovery retains canonical paths and archive validation."""
from pathlib import Path

import pytest

from scripts.core.mars_pipeline import archive_input


@pytest.fixture
def mod_folder(tmp_path, monkeypatch):
    root = tmp_path / "3816401225"
    root.mkdir()
    monkeypatch.setattr(archive_input, "_resolve_allowed_mod_folder", lambda raw: Path(raw))
    return root


def test_discovers_single_archive_without_changing_source(mod_folder):
    archive = mod_folder / "ModContent.fpk"
    archive.write_bytes(b"unchanged")
    assert archive_input.inspect_input(str(mod_folder)) == {
        "kind": "archive", "archive_path": str(archive),
    }
    assert archive.read_bytes() == b"unchanged"


def test_editable_folder_uses_normal_project_import(mod_folder):
    assert archive_input.inspect_input(str(mod_folder))["kind"] == "editable_folder"


def test_multiple_archives_require_explicit_choice(mod_folder):
    for name in ("a.fpk", "b.fpk"):
        (mod_folder / name).write_bytes(b"unchanged")
    with pytest.raises(ValueError, match="multiple"):
        archive_input.inspect_input(str(mod_folder))
    assert archive_input.inspect_input(str(mod_folder / "a.fpk"))["kind"] == "archive"


def test_rejects_redirected_folder(mod_folder, monkeypatch):
    monkeypatch.setattr(archive_input, "_resolve_allowed_mod_folder", lambda raw: mod_folder / "other")
    with pytest.raises(ValueError, match="redirected"):
        archive_input.inspect_input(str(mod_folder))


def test_rejects_directory_disguised_as_archive(mod_folder):
    (mod_folder / "ModContent.fpk").mkdir()
    with pytest.raises(ValueError, match="Choose"):
        archive_input.inspect_input(str(mod_folder))


@pytest.mark.asyncio
async def test_input_inspection_available_to_gui_and_agent(mod_folder):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from scripts.routers.mars_pipeline import router

    app = FastAPI()
    app.include_router(router)
    (mod_folder / "ModContent.fpk").write_bytes(b"not extracted during inspection")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        for prefix in ("/api", "/api/agent"):
            response = await client.post(prefix + "/mars-pipeline/input/inspect", json={"path": str(mod_folder)})
            assert response.status_code == 200
            assert response.json()["kind"] == "archive"
    assert list(mod_folder.iterdir()) == [mod_folder / "ModContent.fpk"]


@pytest.mark.asyncio
async def test_unresolved_candidates_remain_visible_from_persisted_project_options(monkeypatch):
    from scripts.core.mars_pipeline import workflow_delivery

    async def project(_project_id):
        return {"source_path": "unused"}

    monkeypatch.setattr(workflow_delivery, "_project", project)
    monkeypatch.setattr(workflow_delivery, "_outputs", lambda _project: [])
    monkeypatch.setattr(workflow_delivery, "_language_options", lambda: [])
    monkeypatch.setattr(workflow_delivery.store, "project_receipt", lambda _id: {
        "run_id": "saved-run", "delivery_mode": "source_copy", "manifest": {
            "approved_ids": ["1"], "entries": {
                "1": {"text": "Confirmed", "kind": "literal"},
                "2": {"text": "Review later", "kind": "dynamic", "review_reason": "Uncertain mapping",
                      "refs": [{"path": "Code/Test.lua", "line": 3}]},
            },
        },
    })
    result = await workflow_delivery.options("project")
    assert result["source_review_items"] == [{"id": "2", "text": "Review later",
                                              "reason": "Uncertain mapping", "refs": [{"path": "Code/Test.lua", "line": 3}]}]
