from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.core.game_adapters.rimworld import RimWorldAdapter


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPOSITORY_ROOT / ".runtime" / "rimworld-fixture" / "Mod"
KEYED_XML = FIXTURE_ROOT / "Languages" / "English" / "Keyed" / "Keys.xml"
EXPECTED_SHA256 = "00b3b04b87bb4ae107fb1b54f5ee4721ac1ffaa3d8b34241ead8746e28235948"


@pytest.mark.skipif(not KEYED_XML.is_file(), reason="Optional ignored upstream fixture is not present")
def test_external_pawnrules_keyed_xml_round_trips_without_changing_source(tmp_path):
    raw_source = KEYED_XML.read_bytes()
    assert hashlib.sha256(raw_source).hexdigest() == EXPECTED_SHA256

    adapter = RimWorldAdapter()
    discovery = adapter.discover(FIXTURE_ROOT, {"code": "en"}, "1.3")
    resource = next(
        item for item in discovery.resources
        if item.relative_path == "Languages/English/Keyed/Keys.xml"
    )
    document = adapter.parse(resource.path, resource.metadata)
    assert document.entries
    assert not any(item.get("severity") == "error" for item in document.metadata["diagnostics"])

    source_text = raw_source.decode("utf-8")
    no_op = adapter.render(document, {}, {"code": "zh-CN"})
    output_relative_path = "Languages/ChineseSimplified/Keyed/Keys.xml"
    assert no_op == {output_relative_path: source_text}
    assert hashlib.sha256(KEYED_XML.read_bytes()).hexdigest() == EXPECTED_SHA256

    source_entry = next(entry for entry in document.entries if entry.key == "PawnRules.Button.OK")
    translated_text = "确定"
    rendered = adapter.render(document, {source_entry.key: translated_text}, {"code": "zh-CN"})
    assert set(rendered) == {output_relative_path}
    assert "<PawnRules.Button.OK>确定</PawnRules.Button.OK>" in rendered[output_relative_path]
    assert "<PawnRules.Button.Cancel>Cancel</PawnRules.Button.Cancel>" in rendered[output_relative_path]

    target_file = tmp_path / output_relative_path
    target_file.parent.mkdir(parents=True)
    with target_file.open("w", encoding="utf-8", newline="") as handle:
        handle.write(rendered[output_relative_path])
    reread = adapter.parse(target_file, {"kind": "keyed", "relative_output_path": output_relative_path})
    values = {entry.key: entry.value for entry in reread.entries}
    assert values[source_entry.key] == translated_text
    assert values["PawnRules.Button.Cancel"] == "Cancel"
