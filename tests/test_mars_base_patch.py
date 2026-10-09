"""Hybrid origin integrity and recoverable local-only base-game delivery."""
import csv
import io
from types import SimpleNamespace

import pytest

from scripts.core import surviving_mars_csv as adapter
from scripts.core.batch_artifacts import BatchArtifacts
from scripts.core.batch_repository import BatchConflict, BatchRepository
from scripts.core.mars_base_patch_service import MarsBasePatchService, render_patch
from scripts.core.mars_base_patch_validation import community_rows, validate_candidates


def table(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(adapter.HEADER)
    writer.writerows(rows)
    return adapter.parse_text(stream.getvalue())


def candidate(key="1", source="Hello <name>", sc="你好<name>", text="您好<name>", method="zhconvert_taiwan"):
    return {"id": key, "source": source, "official_sc": sc, "translation": text, "method": method,
            "voice_actor": "", "context": ""}


def test_inherited_presentation_allowed_but_dynamic_tokens_never_dropped():
    row = candidate(sc="<em>你好</em><name>\n", text="<em>您好</em><name>\n")
    source = table([["1", row["source"], row["official_sc"], "", ""]])
    converted = {"1": [(row["official_sc"], row["translation"], "conversion") ]}
    report = validate_candidates(source, {"entries": [row]}, {}, converted, {})
    assert report["dynamic_token_integrity"] == "passed"
    assert len(report["inherited_presentation"]) == 1
    row["translation"] = row["translation"].replace("<name>", "")
    converted["1"] = [(row["official_sc"].replace("<name>", ""), row["translation"], "conversion")]
    with pytest.raises(BatchConflict):
        validate_candidates(source, {"entries": [row]}, {}, converted, {})


def test_nested_mars_brackets_preserve_variable_and_allow_label_translation():
    row = candidate(source="[Not available for <duration>]", sc="[不可用<duration>]", text="[無法使用<duration>]")
    source = table([["1", row["source"], row["official_sc"], "", ""]])
    origins = {"1": [(row["official_sc"], row["translation"], "conversion")]}
    assert validate_candidates(source, {"entries": [row]}, {}, origins, {})["entry_count"] == 1
    # A retained converter artifact cannot excuse damage already in the SC reference.
    row["official_sc"] = "[不可用]"
    row["translation"] = "[無法使用]"
    source = table([["1", row["source"], row["official_sc"], "", ""]])
    origins = {"1": [(row["official_sc"], row["translation"], "conversion")]}
    with pytest.raises(BatchConflict, match="Dynamic game tokens"):
        validate_candidates(source, {"entries": [row]}, {}, origins, {})


def test_native_followup_requires_conversion_link_to_the_collected_text():
    row = candidate(text="你好<name>", method="native_luna_needed")
    source = table([["1", row["source"], row["official_sc"], "", ""]])
    native = {"1": [(row["source"], "您好<name>", "native")]}
    converted = {"1": [("您好<name>", row["translation"], "conversion")]}
    assert validate_candidates(source, {"entries": [row]}, {}, converted, native)["entry_count"] == 1
    with pytest.raises(BatchConflict, match="No retained native"):
        validate_candidates(source, {"entries": [row]}, {}, {}, native)


def test_historical_schema_and_source_are_exact():
    rows = community_rows(b"ID,Text,Translation,Extra\n1,Hello,Old,\n")
    assert rows["1"][2] == "Old"
    with pytest.raises(BatchConflict):
        community_rows(b"ID,Text,Translation\n1,Hello,Old\n1,Hello,Old\n")
    row = candidate(method="old_community_exact")
    source = table([["1", row["source"], row["official_sc"], "", ""]])
    with pytest.raises(BatchConflict, match="Historical origin"):
        validate_candidates(source, {"entries": [row]}, rows, {}, {})


def test_duplicate_candidates_and_changed_source_are_rejected():
    row = candidate()
    source = table([["1", row["source"], row["official_sc"], "", ""]])
    with pytest.raises(BatchConflict, match="exactly once"):
        validate_candidates(source, {"entries": [row, row]}, {}, {}, {})
    row["context"] = "changed"
    with pytest.raises(BatchConflict, match="source changed"):
        validate_candidates(source, {"entries": [row]}, {}, {}, {})


@pytest.mark.asyncio
async def test_restart_export_recovery_and_existing_output_protection(tmp_path, monkeypatch):
    from scripts.core import mars_base_patch_service as module
    from scripts.core.batch_artifacts import fingerprint
    async def current(manager, snapshot):
        return None
    monkeypatch.setattr(module, "require_current_sources", current)
    monkeypatch.setattr(module, "read_cover_snapshot", lambda *_: {"data": b"image", "extension": ".jpg"})
    artifacts = BatchArtifacts(tmp_path / "artifacts")
    repository = BatchRepository(tmp_path / "ledger.sqlite")
    row = candidate()
    source = table([["1", row["source"], row["official_sc"], "", ""]])
    candidates = {"entries": [row]}
    metadata = {"mod_id": "RemisMarsHant", "title": "Mars - Traditional Chinese", "description": "Community",
                "short_description": "Patch", "last_changes": "First release", "author": "Author"}
    files = render_patch(source, candidates, metadata, {"data": b"image", "extension": ".jpg"})
    import hashlib
    request = {"metadata": metadata, "cover_asset_path": "cover", "cover_asset_sha256": "snapshot"}
    frozen = {"source_artifact": artifacts.put({"files": [{"content": source.source_text, "selected": True}]}),
              "candidates_artifact": artifacts.put(candidates), "request": request,
              "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    identifier = "mars_base_" + fingerprint(frozen)[:24]
    repository.put("mars_base_plan", {"id": identifier, "project_id": "project", "status": "ready", "frozen": frozen, "validation": {}})
    batch = SimpleNamespace(repository=repository, artifacts=artifacts, manager=None)
    service = MarsBasePatchService(batch, tmp_path / "output")
    with pytest.raises(BatchConflict, match="Approve"):
        await service.export(identifier, False)
    result = await service.export(identifier, True)
    assert result["status"] == "exported"
    restored = MarsBasePatchService(SimpleNamespace(repository=BatchRepository(repository.path), artifacts=artifacts, manager=None), tmp_path / "output")
    assert await restored.export(identifier, True) == result
    destination = result["output_path"]
    from pathlib import Path
    (Path(destination) / "metadata.lua").write_text("user edit", encoding="utf-8")
    with pytest.raises(BatchConflict, match="nothing was overwritten"):
        await restored.export(identifier, True)
    assert (Path(destination) / "metadata.lua").read_text(encoding="utf-8") == "user edit"
    assert "dependencies" not in files["metadata.lua"].decode("utf-8")
    assert "steam_id" not in files["metadata.lua"].decode("utf-8")
