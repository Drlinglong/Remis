"""Smart Workshop writes real structured fixtures through adapter renderers."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.core.game_adapters import workflow_bridge
from scripts.core.game_adapters.registry import resource_adapter
from scripts.core.services.embedded_workshop_service import _load_issues
from scripts.core.services import workshop_writeback_service as writeback


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _allow_validation(monkeypatch):
    monkeypatch.setattr(writeback, "_validation_errors", lambda *args: [])


def test_embedded_workshop_filters_changed_source_translation_marked_for_review(tmp_path):
    source_file = "common/media/lua/shared/Translate/EN/UI.json"
    issues_path = tmp_path / "issues.json"
    issues_path.write_text(json.dumps({"issues": [{
        "source_file": source_file, "file_name": source_file,
        "key": "UI::Greeting", "error_code": "validation_token_mismatch",
        "severity": "error", "source_str": "Source %1", "target_str": "broken",
    }]}), encoding="utf-8")
    protected = [{"source_file": source_file, "key": "UI::Greeting"}]
    assert _load_issues(issues_path, protected) == []


def test_project_zomboid_json_fix_preserves_all_other_values(tmp_path, monkeypatch):
    _allow_validation(monkeypatch)
    path = _write(tmp_path / "common/media/lua/shared/Translate/CH/UI.json",
                  '{\n  "Greeting": "旧文本 %1",\n  "Untouched": "保留原样 \\\"x\\\""\n}\n')
    before = path.read_bytes()
    applied, reason, _ = writeback.apply_validated_workshop_fix_to_path(
        path, "project_zomboid", "UI::Greeting", "Source %1", "新文本 %1", "zh-CN")
    assert (applied, reason) == (True, "validated_and_applied")
    content = path.read_bytes()
    assert content != before
    assert json.loads(content.decode("utf-8")) == {
        "Greeting": "新文本 %1", "Untouched": '保留原样 "x"'}


def test_rimworld_keyed_xml_fix_preserves_xml_structure(tmp_path, monkeypatch):
    _allow_validation(monkeypatch)
    path = _write(tmp_path / "Languages/ChineseSimplified/Keyed/UI.xml",
                  '<?xml version="1.0"?>\n<LanguageData>\n'
                  '  <Greeting>旧文本 &amp; 原样</Greeting>\n'
                  '  <Untouched>保留</Untouched>\n</LanguageData>\n')
    original = path.read_bytes()
    applied, reason, _ = writeback.apply_validated_workshop_fix_to_path(
        path, "rimworld", "Greeting", "Source & value", "新文本 & 原样", "zh-CN")
    assert (applied, reason) == (True, "validated_and_applied")
    assert path.read_bytes() != original
    document = resource_adapter("rimworld").parse(path)
    assert {entry.key: entry.value for entry in document.entries} == {
        "Greeting": "新文本 & 原样", "Untouched": "保留"}
    assert "<Untouched>保留</Untouched>" in path.read_text(encoding="utf-8")


def test_manifest_needs_review_entry_cannot_be_model_repaired(tmp_path, monkeypatch):
    _allow_validation(monkeypatch)
    source = _write(tmp_path / "source/common/media/lua/shared/Translate/EN/UI.json",
                    '{"Greeting":"Source %1"}')
    _write(tmp_path / "source/common/mod.info", "id=repair.example\nname=Repair Fixture\n")
    adapter = resource_adapter("project_zomboid")
    metadata = {"source_root": str(tmp_path / "source"),
                "stable_relative_path": "common/media/lua/shared/Translate/EN/UI.json",
                "category": "UI", "needs_review_keys": ["UI::Greeting"]}
    document = adapter.parse(source, metadata)
    output_root = tmp_path / "output"
    output_path = Path(workflow_bridge.write_document(
        document, adapter.id, ["有待人工确认 %1"], output_root,
        {"code": "zh-CN"})[0])
    before = output_path.read_bytes()
    applied, reason, _ = writeback.apply_validated_workshop_fix_to_path(
        output_path, adapter.id, "UI::Greeting", "Source %1", "自动改写 %1", "zh-CN")
    assert not applied
    assert reason == "writeback_failure"
    assert output_path.read_bytes() == before
