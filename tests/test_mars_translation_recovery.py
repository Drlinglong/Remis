import csv
import io
import json

import pytest

from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.services import mars_translation_recovery as recovery


PROJECT_ID = "project-mars-recovery"


class FakeRegistry:
    def __init__(self):
        self.plan = None
        self.events = []

    def create_plan(self, **kwargs):
        self.plan = {"plan_id": "plan_abcdef0123456789abcdef0123456789",
                     "project_id": kwargs["project_id"], "kind": kwargs["kind"],
                     "execution_args": kwargs["execution_args"]}
        return {**self.plan, "expires_at": "later"}

    def consume_plan(self, plan_id, *, approved):
        if not self.plan or self.plan["plan_id"] != plan_id:
            raise KeyError(plan_id)
        return self.plan

    def release_plan(self, plan_id):
        pass

    def record_event(self, event, **fields):
        self.events.append((event, fields))


class FakeArchive:
    def __init__(self, source, translations):
        self.source = source
        self.translations = translations
        self.changed = False

    def get_latest_version(self, **kwargs):
        return {"id": 31 if not self.changed else 32}

    def get_entries(self, *, project_id, file_path, language):
        return [{"key": key, "original": text, "translation": self.translations[language][key],
                 "file_path": file_path} for key, text in self.source.items()]


SOURCE = {str(700000000001 + index): f"Text {index}" for index in range(88)}


class FakeProjects:
    def __init__(self, source_root):
        self.source_root = source_root
        self.added = []
        self.fail_on_add = False

    async def get_project(self, project_id):
        if project_id != PROJECT_ID:
            return None
        return {"project_id": project_id, "game_id": "surviving_mars",
                "source_path": str(self.source_root), "name": "Mars"}

    async def add_translation_path(self, project_id, path):
        self.added.append(path)
        ProjectJsonManager(str(self.source_root)).add_translation_dir(path)
        if self.fail_on_add:
            raise RuntimeError("index refresh failed")

    async def refresh_project_files(self, project_id):
        return {"files": [{"file_id": language, "file_path": f"{path}/ModTexts.csv",
                            "file_type": "translation"}
                           for language, path in zip(("fr", "de"), self.added)]}

    async def get_project_files(self, project_id):
        return (await self.refresh_project_files(project_id))["files"]


def _setup(tmp_path, monkeypatch, *, tag_mismatch=False):
    source_data = dict(SOURCE)
    source_root = tmp_path / "prepared"
    source_root.mkdir()
    rows = [["ID", "Text", "Translation", "VoiceActor", "Context"]]
    for key, text in SOURCE.items():
        if tag_mismatch and key == "700000000075":
            text = "Growth <em>effect</em>"
            source_data[key] = text
        rows.append([key, text, "", "voice", f"context {key}"])
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\r\n").writerows(rows)
    (source_root / "ModTexts.csv").write_bytes(b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8"))
    ProjectJsonManager(str(source_root)).update_config({"translation_dirs": []})
    translations = {
        language: {key: f"{language.upper()} {text}" for key, text in source_data.items()}
        for language in ("fr", "de")
    }
    if tag_mismatch:
        translations["de"]["700000000075"] = "Deutsches Wachstum"
    monkeypatch.setattr(recovery, "DEST_DIR", str(tmp_path / "outputs"))
    (tmp_path / "outputs").mkdir()
    projects = FakeProjects(source_root)
    registry = FakeRegistry()
    monkeypatch.setattr(recovery, "project_manager", projects)
    monkeypatch.setattr(recovery, "agent_registry", registry)
    monkeypatch.setattr(recovery, "archive_manager", FakeArchive(source_data, translations))
    return source_root, projects, registry


@pytest.mark.asyncio
async def test_plan_and_execute_restore_exact_archived_languages_without_model_calls(tmp_path, monkeypatch):
    source_root, projects, registry = _setup(tmp_path, monkeypatch, tag_mismatch=True)
    preview = await recovery.plan_recovery(PROJECT_ID, ["fr", "de"])
    assert preview["risk"]["may_use_paid_api"] is False
    assert preview["risk"]["overwrites_existing_output"] is False
    assert [item["output_folder_name"] for item in preview["outputs"]] == ["fr-prepared", "de-prepared"]
    assert preview["outputs"][1]["validation_diagnostics"][0]["code"] == "tag_mismatch"

    result = await recovery.execute_recovery(PROJECT_ID, preview["plan_id"], approved=True)
    assert result["status"] == "recovered"
    assert result["runtime_verified"] is False
    for language in ("fr", "de"):
        path = tmp_path / "outputs" / f"{language}-prepared" / "ModTexts.csv"
        raw = path.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
        assert len(rows) == 89
        assert rows[1][1] == SOURCE[rows[1][0]]
        assert rows[1][2] == f"{language.upper()} {SOURCE[rows[1][0]]}"
        assert rows[1][3:] == ["voice", f"context {rows[1][0]}"]
    assert len(projects.added) == 2
    assert registry.events[0][0] == "mars_archived_translation_recovered"


@pytest.mark.asyncio
async def test_recovery_rejects_stale_archive_and_never_overwrites(tmp_path, monkeypatch):
    _, _, registry = _setup(tmp_path, monkeypatch)
    preview = await recovery.plan_recovery(PROJECT_ID, ["fr", "de"])
    recovery.archive_manager.changed = True
    with pytest.raises(recovery.RecoveryError, match="changed after preview"):
        await recovery.execute_recovery(PROJECT_ID, preview["plan_id"], approved=True)
    assert not (tmp_path / "outputs" / "fr-prepared").exists()
    assert not (tmp_path / "outputs" / "de-prepared").exists()


@pytest.mark.asyncio
async def test_registration_failure_rolls_back_both_outputs_and_sidecar(tmp_path, monkeypatch):
    source_root, projects, _ = _setup(tmp_path, monkeypatch)
    projects.fail_on_add = True
    preview = await recovery.plan_recovery(PROJECT_ID, ["fr", "de"])
    with pytest.raises(RuntimeError, match="index refresh failed"):
        await recovery.execute_recovery(PROJECT_ID, preview["plan_id"], approved=True)
    assert not (tmp_path / "outputs" / "fr-prepared").exists()
    assert not (tmp_path / "outputs" / "de-prepared").exists()
    assert ProjectJsonManager(str(source_root)).get_config()["translation_dirs"] == []


@pytest.mark.asyncio
async def test_plan_blocks_archive_source_or_key_mismatch(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    archive = recovery.archive_manager
    original_get_entries = archive.get_entries

    def mismatched(**kwargs):
        rows = original_get_entries(**kwargs)
        rows[0]["original"] = "different source"
        return rows

    archive.get_entries = mismatched
    with pytest.raises(recovery.RecoveryError, match="Archived source text changed"):
        await recovery.plan_recovery(PROJECT_ID, ["fr", "de"])


@pytest.mark.asyncio
async def test_plan_rejects_duplicate_and_unsupported_language_codes(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    with pytest.raises(recovery.RecoveryError, match="unique language codes"):
        await recovery.plan_recovery(PROJECT_ID, ["fr", "fr"])
    with pytest.raises(recovery.RecoveryError, match="not supported"):
        await recovery.plan_recovery(PROJECT_ID, ["xx"])
