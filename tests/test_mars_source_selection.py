"""Language provenance, source-column selection and immutable preparation tests."""
import copy
import csv
import hashlib
import json
import struct
from pathlib import Path

import pytest

from scripts.core.mars_pipeline import delivery, workflow, workflow_store as store
from scripts.core.mars_pipeline.prepare_source import analyze_source
from scripts.core.mars_pipeline.source_selection import select_source, write_prepared_source
from scripts.routers.mars_pipeline import PreparePlan


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "metadata.lua").write_text("return PlaceObj('ModDef', {'id', 'Example', 'title', 'Example'})", encoding="utf-8")
    (root / "code.lua").write_text('local name = T(100000000001, "Colonia lunar")', encoding="utf-8")
    (root / "English.csv").write_text(
        'ID,Text,Translation,VoiceActor,Context\n100000000001,Colonia lunar,Lunar Colony,,Name\n'
        '100000000002,Helio por turno,Helium per Sol,,Resource\n', encoding="utf-8")
    return root


def request(**kwargs):
    return {"source_language": "en", "source_table": "English.csv", "source_column": "Translation",
            "delivery_mode": "text_only", **kwargs}


def test_pivot_preserves_originals_adds_csv_only_ids_and_writes_english(source, tmp_path):
    original = {p.name: p.read_bytes() for p in source.iterdir()}
    manifest = analyze_source(source)
    before = copy.deepcopy(manifest)
    selected = select_source(source, manifest, request())
    assert manifest == before
    assert selected["source_blockers"] == []
    assert selected["entries"]["100000000001"]["text"] == "Colonia lunar"
    assert selected["entries"]["100000000001"]["translation_source_text"] == "Lunar Colony"
    assert selected["entries"]["100000000002"]["identity"] == "existing-t\0" + "100000000002"
    approved, pending = workflow._review(selected, request())
    assert approved == ["100000000001", "100000000002"] and not pending
    output = tmp_path / "prepared"
    write_prepared_source(output, selected, approved)
    with (output / "ModTexts.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["Text"] for row in rows] == ["Lunar Colony", "Helium per Sol"]
    assert all(row["Translation"] == "" for row in rows)
    assert {p.name: p.read_bytes() for p in source.iterdir()} == original
    assert json.loads((output / "mars_lua_manifest.json").read_text(encoding="utf-8"))["source_selection"]["column"] == "Translation"


def test_actual_spanish_source_is_explicit_and_filename_does_not_infer_language(source):
    selected = select_source(source, analyze_source(source), request(source_language="es", source_column="Text"))
    assert selected["source_selection"]["language"] == "es"
    assert selected["entries"]["100000000001"]["translation_source_text"] == "Colonia lunar"
    blocked = select_source(source, analyze_source(source), {})
    assert blocked["source_blockers"][0]["code"] == "source_language_required"
    assert PreparePlan(archive_path="mod.fpk", name="Mod").source_language is None


def test_missing_translation_never_falls_back_to_spanish(source):
    path = source / "English.csv"
    path.write_text(path.read_text(encoding="utf-8").replace(",Lunar Colony,", ",,"), encoding="utf-8")
    selected = select_source(source, analyze_source(source), request())
    assert any(b.get("id") == "100000000001" for b in selected["source_blockers"])


@pytest.mark.parametrize("table", ["../English.csv", "C:/English.csv", "missing.csv", "sub\\English.csv"])
def test_uninspected_and_unsafe_table_paths_fail(source, table):
    with pytest.raises(ValueError, match="source_table"):
        select_source(source, analyze_source(source), request(source_table=table))


def test_pivot_requires_explicit_table_and_is_bound_to_fingerprint(source):
    manifest = analyze_source(source)
    missing = select_source(source, manifest, request(source_table=None))
    assert missing["source_blockers"][0]["code"] == "source_table_required"
    english = select_source(source, manifest, request())
    spanish = select_source(source, manifest, request(source_language="es", source_column="Text"))
    assert store.fingerprint(english) != store.fingerprint(spanish)


def test_text_only_scope_reports_lua_ids_outside_selected_csv(source):
    path = source / "code.lua"
    path.write_text(path.read_text(encoding="utf-8") + '\nlocal range = T(643, "Range")', encoding="utf-8")
    manifest = analyze_source(source)
    selected = select_source(source, manifest, request())
    approved, _ = workflow._review(selected, request())
    assert "643" not in approved
    assert any(d.get("ids") == ["643"] for d in selected["diagnostics"])
    complete = select_source(source, manifest, request(delivery_mode="source_copy"))
    assert any(b.get("id") == "643" for b in complete["source_blockers"])


def test_delivery_checks_selected_source_but_keeps_original_csv_text(source):
    manifest = select_source(source, analyze_source(source), request())
    translated = {"100000000001": "月球殖民地", "100000000002": "每火星日氦产量"}
    assert delivery._language_tables({"zh-CN": translated}, manifest["entries"], set(translated))
    csv_text = delivery._entry_rows(manifest["entries"], translated, set(translated))
    assert "Colonia lunar" in csv_text and "月球殖民地" in csv_text


def flat_archive(source):
    files = [(p.name.encode("utf-8"), p.read_bytes()) for p in sorted(source.iterdir())]
    index_size = sum(16 + len(name) for name, _ in files)
    offset, records, payloads = 32 + index_size, [], []
    for name, data in files:
        records.append(offset.to_bytes(6, "little") + bytes((0x10, len(name)))
                       + struct.pack("<I", len(data)) + name + b"\0" * 4)
        payloads.append(data)
        offset += len(data)
    return b"FLPK" + struct.pack("<7I", 32, 1, 32, 0, index_size, index_size, 4) + b"".join(records + payloads)


@pytest.mark.asyncio
async def test_plan_and_execute_persist_selected_language_and_source(source, tmp_path, monkeypatch):
    archive = tmp_path / "ModContent.fpk"
    archive.write_bytes(flat_archive(source))
    original_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setattr(store, "APP_DATA_DIR", tmp_path / "app")
    monkeypatch.setattr(workflow, "_resolve_allowed_mod_folder", lambda path: Path(path).resolve())
    record = {}
    plan_id = "plan_" + "a" * 32

    def create_plan(**kwargs):
        record.update(kwargs)
        return {"plan_id": plan_id, "expires_at": "later"}

    monkeypatch.setattr(workflow.agent_registry, "create_plan", create_plan)
    monkeypatch.setattr(workflow.agent_registry, "record_event", lambda *a, **k: None)
    plan = await workflow.plan_prepare({**request(source_language="es", source_column="Text"),
                                       "archive_path": str(archive), "name": "Spanish original"})
    assert plan["source_blockers"] == [] and plan["selected_entry_count"] == 2
    monkeypatch.setattr(workflow, "_consume", lambda *_: record)
    created = []

    async def create_project(**kwargs):
        created.append(kwargs)
        return {"project_id": "prepared-project"}

    monkeypatch.setattr(workflow.project_manager, "create_project", create_project)
    result = await workflow.execute_prepare(plan_id, True)
    assert result["status"] == "prepared"
    assert created[0]["source_language"] == "es"
    assert store.read_receipt(plan_id)["source_selection"]["language"] == "es"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == original_hash


@pytest.mark.asyncio
async def test_source_blockers_cannot_be_executed(source, tmp_path, monkeypatch):
    archive = tmp_path / "ModContent.fpk"
    archive.write_bytes(flat_archive(source))
    monkeypatch.setattr(store, "APP_DATA_DIR", tmp_path / "app")
    monkeypatch.setattr(workflow, "_resolve_allowed_mod_folder", lambda path: Path(path).resolve())
    record = {}

    def create_plan(**kwargs):
        record.update(kwargs)
        return {"plan_id": "plan_" + "b" * 32, "expires_at": "later"}

    monkeypatch.setattr(workflow.agent_registry, "create_plan", create_plan)
    plan = await workflow.plan_prepare({"archive_path": str(archive), "name": "Inspect only"})
    assert plan["allowed_actions"] == [] and plan["source_blockers"]
    monkeypatch.setattr(workflow, "_consume", lambda *_: record)
    with pytest.raises(workflow.PackageWorkflowError, match="source language"):
        await workflow.execute_prepare(plan["plan_id"], True)
    assert not (store.root() / "runs" / plan["plan_id"]).exists()


@pytest.mark.asyncio
async def test_dynamic_fallback_does_not_automatically_recommend_full_copy(source, tmp_path, monkeypatch):
    path = source / "code.lua"
    path.write_text(path.read_text(encoding="utf-8") + '\nlocal fallback = Untranslated(place)', encoding="utf-8")
    archive = tmp_path / "ModContent.fpk"
    archive.write_bytes(flat_archive(source))
    monkeypatch.setattr(store, "APP_DATA_DIR", tmp_path / "app")
    monkeypatch.setattr(workflow, "_resolve_allowed_mod_folder", lambda path: Path(path).resolve())
    monkeypatch.setattr(workflow.agent_registry, "create_plan", lambda **_: {
        "plan_id": "plan_" + "c" * 32, "expires_at": "later"})
    plan = await workflow.plan_prepare({**request(), "archive_path": str(archive), "name": "Review fallback"})
    assert plan["hardcoded_entry_count"] == 1
    assert plan["requires_source_review"] is True
    assert plan["recommended_delivery_mode"] is None
    assert plan["allowed_actions"] == ["approve_preparation"]
