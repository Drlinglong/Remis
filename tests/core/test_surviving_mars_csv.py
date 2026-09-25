from __future__ import annotations

import pytest
from pathlib import Path

from scripts.core import surviving_mars_csv
from scripts.core.file_parser import extract_translatable_content_with_diagnostics
from scripts.core.post_processing_manager import PostProcessingManager
from scripts.core.services.file_service import FileService
from scripts.core.services.incremental_snapshot_service import IncrementalSnapshotService
from scripts.core.services.proofreading_service import ProofreadingService
from scripts.core.services.initial_translation_discovery_service import discover_localizable_files


CSV_TEXT = (
    "ID,Text,Translation,VoiceActor,Context\n"
    '1,"Build <em>faster</em>",,Worker,"Tip, shown\\nnow"\n'
    '2,"Need <resource(res)>",,"",\n'
    '3,"Line one\nline two",,Narrator,\n'
)


def _profile() -> dict:
    return {
        "id": "surviving_mars",
        "name": "Surviving Mars / Relaunched",
        "source_localization_folder": ".",
        "format_adapter_id": "surviving_mars_csv",
        "encoding": "utf-8",
        "protected_items": set(),
    }


def test_csv_adapter_preserves_columns_and_multiline_fields() -> None:
    document = surviving_mars_csv.parse_text(CSV_TEXT)
    key_map = {
        index: {"key_part": entry.key, "row_index": entry.row_index}
        for index, entry in enumerate(document.entries)
    }

    rewritten = surviving_mars_csv.rewrite_text(
        CSV_TEXT,
        ["建造 <em>更快</em>", "需要 <resource(res)>", "第一行\n第二行"],
        key_map,
    )
    rows = list(__import__("csv").reader(__import__("io").StringIO(rewritten, newline="")))

    assert rows[0] == list(surviving_mars_csv.HEADER)
    assert rows[1][0] == "1"
    assert rows[1][2] == "建造 <em>更快</em>"
    assert rows[1][3:] == ["Worker", "Tip, shown\\nnow"]
    assert rows[2][2] == "需要 <resource(res)>"
    assert rows[3][1] == "Line one\nline two"
    assert rows[3][2] == "第一行\n第二行"


def test_exact_separator_directive_preserves_prefix_bom_row_indexes_and_line_numbers(tmp_path: Path) -> None:
    table_path = tmp_path / "ModTexts.csv"
    source = (
        "\ufeffsep=,\r\n"
        "ID,Text,Translation,VoiceActor,Context\r\n"
        '000123,"First line\r\nsecond line",,"Voice A","Context, one"\r\n'
        '000002,"Need <resource(res)>","已有译文",,"Keep tag"\r\n'
    )
    source_bytes = source.encode("utf-8")
    table_path.write_bytes(source_bytes)

    assert surviving_mars_csv.is_table_file(table_path)
    document = surviving_mars_csv.parse_file(table_path)
    assert document.header_row_index == 1
    assert document.data_row_count == 2
    assert [entry.key for entry in document.entries] == ["000123", "000002"]
    assert [entry.row_index for entry in document.entries] == [2, 3]
    assert [entry.line_number for entry in document.entries] == [4, 5]
    assert surviving_mars_csv.parse_summary(document) == {
        "raw": 2, "syntax_parsed": 2, "policy_excluded": 0,
        "eligible": 2, "parse_errors": 0,
    }

    lines, texts, key_map = surviving_mars_csv.extract_file(table_path)
    assert len(lines) == 5
    assert texts == ["First line\r\nsecond line", "Need <resource(res)>"]
    assert key_map[0]["line_num"] == 3
    assert key_map[0]["row_index"] == 2
    assert [item.key for item in surviving_mars_csv.entries(table_path)] == ["000123", "000002"]
    translated_entries = surviving_mars_csv.entries(table_path, "Translation")
    assert [(item.key, item.value, item.line_number) for item in translated_entries] == [
        ("000002", "已有译文", 5),
    ]
    assert table_path.read_bytes() == source_bytes

    rewritten = surviving_mars_csv.rewrite_text(
        document.source_text,
        ["第一行\r\n第二行", "需要 <resource(res)>"],
        {index: {"key_part": entry.key, "row_index": entry.row_index}
         for index, entry in enumerate(document.entries)},
    )
    assert rewritten.startswith("sep=,\r\nID,Text,Translation,VoiceActor,Context\r\n")
    assert not rewritten.startswith("\ufeff")
    assert "\r\n" in rewritten
    result = surviving_mars_csv.parse_text(rewritten)
    assert [entry.key for entry in result.entries] == ["000123", "000002"]
    assert [entry.line_number for entry in result.entries] == [5, 6]
    assert [row[2] for row in result.rows[2:]] == ["第一行\r\n第二行", "需要 <resource(res)>"]
    assert result.rows[2][0] == "000123"
    assert result.rows[2][3:] == ("Voice A", "Context, one")
    assert surviving_mars_csv.compare_tags("<resource(res)>", "<resource(res)>").is_mismatch is False


@pytest.mark.parametrize("prefix,header", [
    ("sep=;\n", "ID,Text,Translation,VoiceActor,Context\n"),
    ("sep=,\n", "ID,Text,Translation,VoiceActor,Other\n"),
    ('"sep=",\n', "ID,Text,Translation,VoiceActor,Context\n"),
])
def test_separator_directive_only_accepts_exact_prefix_and_strict_header(
    tmp_path: Path, prefix: str, header: str,
) -> None:
    table_path = tmp_path / "Invalid.csv"
    table_path.write_text(prefix + header + "001,Text,,,,\n", encoding="utf-8", newline="")

    assert surviving_mars_csv.is_table_file(table_path) is False
    with pytest.raises(surviving_mars_csv.NotSurvivingMarsCsv):
        surviving_mars_csv.parse_file(table_path)


def test_file_parser_and_discovery_use_moditem_table_schema(tmp_path: Path) -> None:
    table_path = tmp_path / "nested" / "Game.csv"
    table_path.parent.mkdir()
    table_path.write_text(CSV_TEXT, encoding="utf-8", newline="")
    (tmp_path / "ordinary.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    lines, texts, key_map, diagnostics = extract_translatable_content_with_diagnostics(str(table_path))
    assert len(lines) == 5
    assert texts == ["Build <em>faster</em>", "Need <resource(res)>", "Line one\nline two"]
    assert [key_map[index]["key_part"] for index in range(3)] == ["1", "2", "3"]
    assert diagnostics == ()

    discovered = discover_localizable_files(
        "ignored",
        _profile(),
        {"key": "l_english", "name": "English"},
        override_path=str(tmp_path),
    )
    assert [item["file_path"] for item in discovered] == ["nested/Game.csv"]


def test_file_service_and_incremental_snapshot_only_include_table_csv(tmp_path: Path) -> None:
    table_path = tmp_path / "Game.csv"
    table_path.write_text(CSV_TEXT, encoding="utf-8", newline="")
    (tmp_path / "ordinary.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    manifest = FileService().discover_files(
        project_id="project",
        source_path=str(tmp_path),
        translation_dirs=[],
        source_language="en",
        game_id="surviving_mars",
    )
    assert [Path(item["file_path"]).name for item in manifest["files"]] == ["Game.csv"]

    snapshot = IncrementalSnapshotService().build_snapshot(
        str(tmp_path),
        {"name_en": "English"},
        game_profile=_profile(),
    )
    assert len(snapshot) == 1
    assert snapshot[0]["file_path"] == "Game.csv"
    assert snapshot[0]["parsed_entries"][0][0] == "1"


def test_post_processing_validates_exact_runtime_tags(tmp_path: Path) -> None:
    source_path = tmp_path / "source" / "Game.csv"
    output_path = tmp_path / "output" / "Game.csv"
    source_path.parent.mkdir()
    output_path.parent.mkdir()
    source_path.write_text(CSV_TEXT, encoding="utf-8", newline="")
    source_document = surviving_mars_csv.parse_text(CSV_TEXT)
    source_key_map = {
        index: {"key_part": entry.key, "row_index": entry.row_index}
        for index, entry in enumerate(source_document.entries)
    }
    output_path.write_text(
        surviving_mars_csv.rewrite_text(
            CSV_TEXT,
            ["Build <em>faster</em>", "Need <resource(other)>", "Line one\nline two"],
            source_key_map,
        ),
        encoding="utf-8",
        newline="",
    )

    manager = PostProcessingManager(_profile(), str(output_path.parent), str(source_path.parent))
    assert manager.run_validation(
        {"key": "l_simp_chinese", "code": "zh-CN"},
        {"key": "l_english", "code": "en"},
    )
    stats = manager.get_validation_stats()
    assert stats["total_errors"] == 1
    assert str(output_path) in manager.validation_results


class _ProofreadingProjectManager:
    def __init__(self, project, files):
        self.project = project
        self.files = files
        self.status_updates = []

    async def get_project(self, _project_id):
        return self.project

    async def get_project_files(self, _project_id):
        return self.files

    async def update_file_status_with_kanban_sync(self, project_id, file_id, status):
        self.status_updates.append((project_id, file_id, status))


class _ProofreadingArchive:
    def __init__(self):
        self.updates = []

    def get_entries(self, **_kwargs):
        return [{"key": "1", "translation": "来自档案"}]

    def update_translations(self, *args, **kwargs):
        self.updates.append((args, kwargs))
        return len(args[2])


@pytest.mark.asyncio
async def test_proofreading_reads_and_writes_only_translation_column(tmp_path: Path) -> None:
    source_path = tmp_path / "source" / "Game.csv"
    target_path = tmp_path / "output" / "Game.csv"
    source_path.parent.mkdir()
    target_path.parent.mkdir()
    source_path.write_text(CSV_TEXT, encoding="utf-8", newline="")
    source_document = surviving_mars_csv.parse_text(CSV_TEXT)
    target_path.write_text(
        surviving_mars_csv.rewrite_text(
            CSV_TEXT,
            ["已有译文", "", "第三行译文"],
            {
                index: {"key_part": entry.key, "row_index": entry.row_index}
                for index, entry in enumerate(source_document.entries)
            },
        ),
        encoding="utf-8",
        newline="",
    )
    project = {
        "project_id": "project",
        "name": "Mars Mod",
        "source_path": str(source_path.parent),
        "source_language": "en",
    }
    project_manager = _ProofreadingProjectManager(
        project,
        [{"file_id": "file", "file_path": str(target_path)}],
    )
    archive = _ProofreadingArchive()
    service = ProofreadingService(project_manager, archive)

    data = await service.get_proofread_data("project", "file")

    assert [row["key"] for row in data["rows"]] == ["1", "2", "3"]
    assert data["rows"][0]["final_value"] == "已有译文"
    assert data["rows"][1]["final_value"].startswith("⚠️ [DB_MISSING]")
    assert "VoiceActor" in data["final_content"]

    result = await service.save_proofread_data(
        "project",
        "file",
        [
            {"key": "1", "translation": "最终一"},
            {"key": "2", "translation": "最终二"},
            {"key": "3", "translation": "最终三"},
        ],
    )

    assert result["status"] == "success"
    assert not target_path.read_bytes().startswith(b"\xef\xbb\xbf")
    written = surviving_mars_csv.parse_file(target_path)
    assert [entry.value for entry in surviving_mars_csv.entries(target_path, "Translation")] == [
        "最终一", "最终二", "最终三"
    ]
    assert written.rows[1][3:] == source_document.rows[1][3:]
    assert project_manager.status_updates == [("project", "file", "done")]
    assert len(archive.updates) == 1
def test_separator_header_cannot_be_targeted_by_a_translation_key_map():
    source = "sep=,\nID,Text,Translation,VoiceActor,Context\n001,Source,,,\n"
    with pytest.raises(surviving_mars_csv.SurvivingMarsCsvError, match="Invalid row index"):
        surviving_mars_csv.rewrite_text(source, ["bad"], {0: {"row_index": 1, "key_part": "ID"}})
