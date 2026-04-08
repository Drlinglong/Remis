from pathlib import Path

import pytest

from scripts.core.services.proofreading_service import ProofreadingService


class FakeProjectManager:
    def __init__(self, files=None, project=None):
        self.files = files or []
        self.project = project or {}
        self.get_project_files_calls = 0
        self.get_project_calls = 0

    async def get_project_files(self, project_id):
        self.get_project_files_calls += 1
        return self.files

    async def get_project(self, project_id):
        self.get_project_calls += 1
        return self.project


@pytest.mark.asyncio
async def test_find_source_template_prefers_direct_path_rewrite(monkeypatch):
    source_file = "J:/repo/mod/localization/english/events_l_english.yml"
    target_file = "J:/repo/mod/localization/simp_chinese/events_l_simp_chinese.yml"

    manager = FakeProjectManager()
    service = ProofreadingService(manager, archive_manager=None)

    monkeypatch.setattr(Path, "exists", lambda self: str(self).replace("\\", "/") == source_file)
    monkeypatch.setattr(
        service.project_manager,
        "get_project_files",
        manager.get_project_files,
    )

    result = await service.find_source_template(target_file, "english", "simp_chinese")

    assert result.replace("\\", "/") == source_file
    assert manager.get_project_files_calls == 0
    assert manager.get_project_calls == 0


@pytest.mark.asyncio
async def test_find_source_template_falls_back_to_project_file_index(monkeypatch):
    indexed_source = "J:/repo/indexed/events_l_english.yml"

    manager = FakeProjectManager(
        files=[{"file_path": indexed_source}],
        project={"source_path": "J:/repo/source-root"},
    )
    service = ProofreadingService(manager, archive_manager=None)

    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(
        service.project_manager,
        "get_project_files",
        manager.get_project_files,
    )
    monkeypatch.setattr(
        service.project_manager,
        "get_project",
        manager.get_project,
    )
    monkeypatch.setattr(
        __import__("os").path,
        "exists",
        lambda path: path == indexed_source,
    )

    result = await service.find_source_template(
        "J:/repo/missing/events_l_simp_chinese.yml",
        "english",
        "simp_chinese",
        project_id="p1",
    )

    assert result == indexed_source
    assert manager.get_project_files_calls == 1
    assert manager.get_project_calls == 0


@pytest.mark.asyncio
async def test_find_source_template_falls_back_to_disk_search(monkeypatch):
    source_root = "J:/repo/source-root"
    nested_source = "J:/repo/source-root/subdir/events_l_english.yml"

    manager = FakeProjectManager(files=[], project={"source_path": source_root})
    service = ProofreadingService(manager, archive_manager=None)

    monkeypatch.setattr(Path, "exists", lambda self: False)
    monkeypatch.setattr(
        service.project_manager,
        "get_project_files",
        manager.get_project_files,
    )
    monkeypatch.setattr(
        service.project_manager,
        "get_project",
        manager.get_project,
    )
    monkeypatch.setattr(
        __import__("os").path,
        "exists",
        lambda path: path == source_root,
    )
    monkeypatch.setattr(
        __import__("os"),
        "walk",
        lambda root: [(f"{source_root}/subdir", [], ["events_l_english.yml"])],
    )

    result = await service.find_source_template(
        "J:/repo/missing/events_l_simp_chinese.yml",
        "english",
        "simp_chinese",
        project_id="p1",
    )

    assert result.replace("\\", "/") == nested_source
    assert manager.get_project_files_calls == 1
    assert manager.get_project_calls == 1
