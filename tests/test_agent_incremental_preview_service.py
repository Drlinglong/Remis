import csv
from pathlib import Path

import pytest

from scripts.core.services import incremental_preparation_service
from scripts.core.services.agent_incremental_preview_service import build_incremental_preview


def _write_table(path: Path, entries: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("ID", "Text", "Translation", "VoiceActor", "Context"))
        writer.writerows((key, text, "", "", "") for key, text in entries)


class _Archive:
    def __init__(self, entries=None):
        self.entries = entries or {}

    def get_entries(self, *, project_id, language):
        return list(self.entries.get(language, []))

    def get_latest_version(self, **_kwargs):
        return None


class _ProjectManager:
    async def get_project(self, project_id):
        if project_id != "p1":
            return None
        return {"project_id": project_id, "game_id": "surviving_mars", "source_language": "en"}


def _archive(monkeypatch, entries):
    monkeypatch.setattr(
        "scripts.core.services.agent_incremental_preview_service.IncrementalArchiveService",
        lambda: type("ArchiveService", (), {
            "get_language_entries": lambda self, project_id, language_code: list(entries.get(language_code, [])),
        })(),
    )


@pytest.mark.asyncio
async def test_new_and_modified_entries_are_classified_without_output_writes(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write_table(source / "table.csv", [(str(i), f"text {i}") for i in range(1, 7)])
    _archive(monkeypatch, {"zh-CN": [
        {"file_path": "table.csv", "key": "2", "original": "old text", "translation": "译2"},
    ]})

    result = await build_incremental_preview("p1", source, ["zh-CN"], project_manager=_ProjectManager())

    assert result["summary"] == {
        "total": 6, "new": 5, "changed": 1, "unchanged": 0,
        "deleted": 0, "model_submitted": 6, "review_required": 0,
    }
    assert result["languages"][0]["file_summaries"][0]["dirty_entries"]
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.asyncio
async def test_171_entry_revision_preserves_165_translations(tmp_path, monkeypatch):
    source = tmp_path / "v42"
    _write_table(source / "ModTexts.csv", [(str(i), f"text {i}") for i in range(1, 172)])
    baseline = [{"file_path": "ModTexts.csv", "key": str(i), "original": f"text {i}",
                 "translation": f"译文 {i}"} for i in range(1, 167)]
    baseline[-1]["original"] = "previous revision"
    _archive(monkeypatch, {"zh-CN": baseline})
    result = await build_incremental_preview("p1", source, ["zh-CN"], project_manager=_ProjectManager())
    assert result["summary"] == dict(total=171, new=5, changed=1, unchanged=165, deleted=0,
                                     model_submitted=6, review_required=0)
    dirty = result["file_summaries"][0]["dirty_entries"]
    assert [item["key"] for item in dirty] == [str(i) for i in range(166, 172)]
    assert dirty[0]["reason"] == "source_modified"
    assert dirty[0]["previous_source_text"] == "previous revision"


@pytest.mark.asyncio
async def test_removed_entries_missing_translations_and_moved_unique_key(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write_table(source / "new" / "table.csv", [("2", "kept"), ("3", "changed")])
    _archive(monkeypatch, {"zh-CN": [
        {"file_path": "old/table.csv", "key": "1", "original": "removed", "translation": "译"},
        {"file_path": "old/table.csv", "key": "2", "original": "kept", "translation": "译"},
        {"file_path": "new/table.csv", "key": "3", "original": "changed", "translation": ""},
    ]})

    result = await build_incremental_preview("p1", source, ["zh-CN"], project_manager=_ProjectManager())
    lang = result["languages"][0]
    assert (lang["unchanged"], lang["changed"], lang["deleted"]) == (1, 1, 1)
    assert lang["model_submitted"] == 1
    assert lang["deleted_entries"][0]["key"] == "1"


@pytest.mark.asyncio
async def test_no_baseline_marks_all_new_and_fingerprint_tracks_translation(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write_table(source / "table.csv", [("1", "one")])
    entries = {"zh-CN": []}
    _archive(monkeypatch, entries)
    first = await build_incremental_preview("p1", source, ["zh-CN"], project_manager=_ProjectManager())
    assert first["summary"]["new"] == 1

    entries["zh-CN"] = [{"file_path": "table.csv", "key": "1", "original": "one", "translation": "译文甲"}]
    second = await build_incremental_preview("p1", source, ["zh-CN"], project_manager=_ProjectManager())
    entries["zh-CN"][0]["translation"] = "译文乙"
    third = await build_incremental_preview("p1", source, ["zh-CN"], project_manager=_ProjectManager())
    assert second["fingerprint"] != first["fingerprint"]
    assert third["fingerprint"] != second["fingerprint"]


@pytest.mark.asyncio
async def test_adapter_review_classification_is_counted(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write_table(source / "table.csv", [("1", "changed")])
    _archive(monkeypatch, {"zh-CN": [
        {"file_path": "table.csv", "key": "1", "original": "old", "translation": "保留"},
    ]})
    original = incremental_preparation_service._prepare_file_entries

    def with_adapter_review(file_data, *args, **kwargs):
        file_data["adapter_key_map"] = {"1": {}}
        return original(file_data, *args, **kwargs)

    monkeypatch.setattr(incremental_preparation_service, "_prepare_file_entries", with_adapter_review)
    # The function was imported by the preview service; patch its module global too.
    monkeypatch.setattr(
        "scripts.core.services.agent_incremental_preview_service._prepare_file_entries",
        with_adapter_review,
    )
    monkeypatch.setattr("scripts.core.game_adapters.review_state.pending_keys", lambda *_args: set())

    result = await build_incremental_preview("p1", source, ["zh-CN"], project_manager=_ProjectManager())
    assert result["summary"]["review_required"] == 1
    assert result["summary"]["model_submitted"] == 0


@pytest.mark.asyncio
async def test_missing_project_source_directory_and_empty_source_fail(tmp_path):
    with pytest.raises(FileNotFoundError):
        await build_incremental_preview("missing", tmp_path, ["zh-CN"], project_manager=_ProjectManager())
    with pytest.raises(FileNotFoundError):
        await build_incremental_preview("p1", tmp_path / "absent", ["zh-CN"], project_manager=_ProjectManager())
    with pytest.raises(ValueError, match="no eligible"):
        await build_incremental_preview("p1", tmp_path, ["zh-CN"], project_manager=_ProjectManager())
