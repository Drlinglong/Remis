from pathlib import Path

import pytest

from scripts.core.services.proofreading_service import ProofreadingDataError, ProofreadingService


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


@pytest.mark.asyncio
async def test_get_proofread_data_reports_missing_indexed_file(monkeypatch):
    manager = FakeProjectManager(
        project={"project_id": "p1", "name": "Demo", "source_language": "en"},
        files=[
            {
                "file_id": "f1",
                "file_path": "J:/missing/localization/simp_chinese/demo_l_simp_chinese.yml",
            }
        ],
    )
    service = ProofreadingService(manager, archive_manager=None)

    monkeypatch.setattr(__import__("os").path, "exists", lambda path: False)

    with pytest.raises(ProofreadingDataError) as exc_info:
        await service.get_proofread_data("p1", "f1")

    assert exc_info.value.code == "file_path_not_found"
    assert "indexed localization file no longer exists" in exc_info.value.message


def test_build_proofreading_rows_preserves_structure_lines():
    service = ProofreadingService(project_manager=None, archive_manager=None)
    original_lines = [
        "l_english:\n",
        " # Intro comment\n",
        " # Second comment\n",
        "\n",
        "\n",
        " demo.key:0 \"Original\"\n",
        " plain_structure = yes\n",
    ]
    texts_to_translate = ["Original"]
    key_map = {
        0: {
            "key_part": "demo.key:0",
            "line_num": 5,
        }
    }

    rows = service._build_proofreading_rows(
        original_lines,
        texts_to_translate,
        key_map,
        ["AI draft"],
        ["Final text"],
    )

    assert [row["row_type"] for row in rows] == ["structure", "structure", "structure", "translation", "structure"]
    assert rows[0]["structure_type"] == "header"
    assert rows[1]["structure_type"] == "comment"
    assert rows[1]["line_start"] == 2
    assert rows[1]["line_end"] == 3
    assert rows[1]["editable"] is True
    assert rows[1]["final_value"] == " # Intro comment\n # Second comment"
    assert rows[2]["structure_type"] == "blank"
    assert rows[2]["line_start"] == 4
    assert rows[2]["line_end"] == 5
    assert rows[3]["key"] == "demo.key:0"
    assert rows[3]["source_value"] == "Original"
    assert rows[3]["ai_value"] == "AI draft"
    assert rows[3]["final_value"] == "Final text"
    assert rows[3]["editable"] is True
    assert rows[4]["structure_type"] == "raw"


def test_build_proofreading_rows_aligns_target_comments_by_block_order():
    service = ProofreadingService(project_manager=None, archive_manager=None)
    original_lines = [
        "l_english:\n",
        " # Source comment\n",
        " demo.key:0 \"Original\"\n",
    ]
    target_lines = [
        "l_simp_chinese:\n",
        " # Edited comment\n",
        " # Added comment line\n",
        " demo.key:0 \"Translation\"\n",
    ]

    rows = service._build_proofreading_rows(
        original_lines,
        ["Original"],
        {0: {"key_part": "demo.key:0", "line_num": 2}},
        ["AI draft"],
        ["Translation"],
        target_lines,
    )

    comment_row = next(row for row in rows if row.get("structure_type") == "comment")
    assert comment_row["final_value"] == " # Edited comment\n # Added comment line"


def test_build_preserved_comment_patches_uses_source_ranges_and_target_content():
    service = ProofreadingService(project_manager=None, archive_manager=None)
    patches = service._build_preserved_comment_patches(
        ["l_english:\n", " # Source\n", " demo.key:0 \"Text\"\n"],
        ["l_simp_chinese:\n", " # Edited\n", " # Added\n", " demo.key:0 \"译文\"\n"],
    )

    assert patches == [{
        "entry_id": "preserved-comment-1-1",
        "line_start": 2,
        "line_end": 2,
        "content": " # Edited\n # Added",
    }]


def test_apply_structure_patches_only_changes_comment_blocks():
    service = ProofreadingService(project_manager=None, archive_manager=None)
    lines = [
        "l_english:\n",
        " # Old comment\n",
        " # Second line\n",
        " demo.key:0 \"Text\"\n",
    ]

    patched = service._apply_structure_patches(
        lines,
        [{"line_start": 2, "line_end": 3, "content": " # New comment\n # Kept together"}],
    )

    assert patched == [
        "l_english:\n",
        " # New comment\n",
        " # Kept together\n",
        " demo.key:0 \"Text\"\n",
    ]


def test_apply_structure_patches_rejects_non_comment_ranges():
    service = ProofreadingService(project_manager=None, archive_manager=None)

    with pytest.raises(ValueError, match="Only comment rows"):
        service._apply_structure_patches(
            ["l_english:\n", " demo.key:0 \"Text\"\n"],
            [{"line_start": 1, "line_end": 1, "content": "# Not a header"}],
        )
