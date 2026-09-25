"""Focused approval, identity, receipt, and output-boundary tests."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.core.mars_pipeline import workflow, workflow_delivery, workflow_store as store
from scripts.core.services.translation_package_workflow import PackageWorkflowError
from scripts.routers.mars_pipeline import DeliveryPlan


def test_translation_reports_are_not_treated_as_localization_tables(tmp_path, monkeypatch):
    folder = tmp_path / "zh-CN-example"
    folder.mkdir()
    (folder / "ModTexts.csv").write_text(
        "ID,Text,Translation,VoiceActor,Context\n1,English,Chinese,,\n", encoding="utf-8")
    (folder / "format_validation_report.csv").write_text("File,Line,Level\n", encoding="utf-8")
    (folder / "Proofreading Progress.csv").write_text("Status,Source File\n", encoding="utf-8")
    monkeypatch.setattr(workflow_delivery, "_outputs", lambda _: [
        {"output_folder_name": folder.name, "language_code": "zh-CN"}])
    monkeypatch.setattr(workflow_delivery, "_select_output", lambda *_: folder)
    result = workflow_delivery._read_translations({}, {"entries": {"1": {"text": "English"}}}, [
        {"output_folder_name": folder.name, "language_code": "zh-CN"}])
    assert result == {"zh-CN": {"1": "Chinese"}}


def test_text_only_needs_only_existing_t_translations_while_source_copy_needs_all(
    tmp_path, monkeypatch,
):
    folder = tmp_path / "zh-CN-example"
    folder.mkdir()
    (folder / "ModTexts.csv").write_text(
        "ID,Text,Translation,VoiceActor,Context\n"
        "1,Existing keyed text,已翻译,,\n"
        "2,Hardcoded Lua text,,,\n",
        encoding="utf-8",
    )
    project = {"project_id": "project", "outputs_root": str(tmp_path)}
    manifest = {"approved_ids": ["1", "2"], "entries": {
        "1": {"kind": "existing_t", "text": "Existing keyed text"},
        "2": {"kind": "literal", "text": "Hardcoded Lua text"},
    }}
    monkeypatch.setattr(workflow_delivery, "_outputs", lambda _: [
        {"output_folder_name": folder.name, "language_code": "zh-CN"}])
    monkeypatch.setattr(workflow_delivery, "_select_output", lambda *_: folder)
    selections = [{"output_folder_name": folder.name, "language_code": "zh-CN"}]

    assert workflow_delivery._read_translations(project, manifest, selections, "text_only") == {
        "zh-CN": {"1": "已翻译"}}
    with pytest.raises(ValueError, match="Translation is empty for ID 2"):
        workflow_delivery._read_translations(project, manifest, selections, "source_copy")


def test_text_only_preparation_selects_only_existing_localization_ids():
    approved, pending = workflow._review({"entries": {
        "1": {"kind": "existing_t", "text": "English"},
        "2": {"kind": "literal", "text": "Hardcoded"},
    }}, {"delivery_mode": "text_only"})
    assert approved == ["1"]
    assert pending == []


def _raw_archive() -> bytes:
    name = b"x.bin"
    record = (b"\0" * 6 + bytes((0x10, len(name))) + struct.pack("<I", 1)
              + name + b"\0" * 4)
    offset = 32 + len(record)
    record = offset.to_bytes(6, "little") + record[6:]
    return b"FLPK" + struct.pack("<7I", 32, 1, 32, 0, len(record), len(record), 4) + record + b"x"


def _ready_manifest() -> dict:
    return {
        "mod_id": "mars-mod-1",
        "source_fingerprint": "source-fingerprint",
        "entries": {
            "1": {"text": "Automatic text", "review_required": False, "refs": []},
            "2": {"text": "Manual text", "review_required": True,
                  "review_reason": "needs a person", "refs": []},
            "3": {"text": "Another manual text", "review_required": True,
                  "review_reason": "needs a person", "refs": []},
        },
        "diagnostics": [],
    }


def test_archive_path_uses_the_canonical_allowed_parent(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    archive = allowed / "ModContent.fpk"
    archive.write_bytes(_raw_archive())
    monkeypatch.setattr(workflow, "_resolve_allowed_mod_folder", lambda _path: allowed)

    assert workflow._archive_path(str(archive)) == archive

    redirected_parent = tmp_path / "other"
    redirected_parent.mkdir()
    monkeypatch.setattr(workflow, "_resolve_allowed_mod_folder", lambda _path: redirected_parent)
    with pytest.raises(ValueError, match="canonical allowed parent"):
        workflow._archive_path(str(archive))


@pytest.fixture
def pipeline_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "APP_DATA_DIR", tmp_path / "app-data")
    return tmp_path / "app-data" / "mars_pipeline"


@pytest.mark.asyncio
async def test_prepare_plan_requires_approval_and_records_source_copy_choices(
    tmp_path, monkeypatch, pipeline_store,
):
    archive_path = tmp_path / "ModContent.fpk"
    archive_path.write_bytes(_raw_archive())
    monkeypatch.setattr(workflow, "_resolve_allowed_mod_folder", lambda path: Path(path))
    monkeypatch.setattr(workflow, "_inspect", lambda _request: (
        {"archive_sha256": "a" * 64, "files": [{"path": "x.bin"}]}, _ready_manifest(),
    ))
    captured = {}

    def create_plan(**kwargs):
        captured.update(kwargs)
        return {"plan_id": "plan_" + "1" * 32, "expires_at": "later"}

    monkeypatch.setattr(workflow.agent_registry, "create_plan", create_plan)
    result = await workflow.plan_prepare({
        "archive_path": str(archive_path), "name": "Mars mod",
        "approved_ids": ["2"],
    })

    assert result["requires_approval"] is True
    assert result["allowed_actions"] == ["approve_preparation"]
    assert result["approved_ids"] == ["1", "2"]
    assert [item["id"] for item in result["review_items"]] == ["3"]
    assert captured["kind"] == "mars_pipeline_prepare"
    assert captured["execution_args"]["archive_sha256"] == "a" * 64
    assert captured["execution_args"]["approved_ids"] == ["1", "2"]


@pytest.mark.asyncio
async def test_prepare_rejects_missing_approval_before_creating_run(pipeline_store):
    with pytest.raises(PackageWorkflowError) as caught:
        await workflow.execute_prepare("plan_" + "2" * 32, approved=False)
    assert caught.value.code == "approval_required"
    assert not (pipeline_store / "runs").exists()


@pytest.mark.asyncio
async def test_prepare_rejects_wrong_plan_kind_and_releases_it(
    monkeypatch, pipeline_store,
):
    released = []
    monkeypatch.setattr(workflow, "_consume", lambda *_args: {"kind": "translation"})
    monkeypatch.setattr(workflow.agent_registry, "release_plan", released.append)

    with pytest.raises(PackageWorkflowError) as caught:
        await workflow.execute_prepare("plan_" + "3" * 32, approved=True)

    assert caught.value.code == "invalid_plan"
    assert released == ["plan_" + "3" * 32]
    assert not (pipeline_store / "runs").exists()


@pytest.mark.asyncio
async def test_prepare_stale_archive_hash_leaves_failed_receipt_without_project(
    tmp_path, monkeypatch, pipeline_store,
):
    archive_path = tmp_path / "ModContent.fpk"
    original = _raw_archive()
    archive_path.write_bytes(original)
    plan_id = "plan_" + "4" * 32
    manifest = _ready_manifest()
    original_hash = hashlib.sha256(original).hexdigest()
    execution_args = {
        "archive_path": str(archive_path), "archive_sha256": original_hash,
        "manifest_fingerprint": store.fingerprint(manifest), "approved_ids": ["1"],
        "name": "Mars mod",
    }
    monkeypatch.setattr(workflow, "_resolve_allowed_mod_folder", lambda path: Path(path))
    monkeypatch.setattr(workflow, "_inspect", lambda _request: (
        {"archive_sha256": original_hash, "files": [{"path": "x.bin"}]}, manifest,
    ))
    monkeypatch.setattr(workflow, "_consume", lambda *_args: {
        "kind": "mars_pipeline_prepare", "execution_args": execution_args,
    })
    create_project = []

    async def create_project_mock(**kwargs):
        create_project.append(kwargs)
        return {"project_id": "project-created"}

    monkeypatch.setattr(workflow.project_manager, "create_project", create_project_mock)
    archive_path.write_bytes(original[:-1] + b"y")

    with pytest.raises(ValueError, match="SHA-256"):
        await workflow.execute_prepare(plan_id, approved=True)

    receipt = store.read_receipt(plan_id)
    assert receipt["status"] == "failed"
    assert receipt["archive_sha256"] == original_hash
    assert create_project == []
    assert not (store.run_path(plan_id) / "source").exists()


@pytest.mark.asyncio
async def test_prepare_success_persists_project_manager_project_id(
    tmp_path, monkeypatch, pipeline_store,
):
    archive_path = tmp_path / "ModContent.fpk"
    archive_path.write_bytes(_raw_archive())
    plan_id = "plan_" + "f" * 32
    manifest = _ready_manifest()
    archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    execution_args = {
        "archive_path": str(archive_path), "archive_sha256": archive_hash,
        "manifest_fingerprint": store.fingerprint(manifest), "approved_ids": ["1", "2"],
        "name": "Mars mod",
    }
    monkeypatch.setattr(workflow, "_archive_path", lambda _path: archive_path)
    monkeypatch.setattr(workflow, "_consume", lambda *_args: {
        "kind": "mars_pipeline_prepare", "execution_args": execution_args,
    })

    def extract_mock(_archive_path, destination, *, expected_sha256):
        assert expected_sha256 == archive_hash
        destination.mkdir(parents=True)
        (destination / "metadata.lua").write_text("return {}", encoding="utf-8")
        return {"archive_sha256": archive_hash, "files": [{"path": "metadata.lua"}]}

    monkeypatch.setattr(workflow, "extract_archive", extract_mock)
    monkeypatch.setattr(workflow, "analyze_source", lambda *_args: manifest)

    def prepare_mock(_source, destination, _previous, **kwargs):
        assert kwargs == {"mode": "overlay", "approved_ids": ["1", "2"]}
        destination.mkdir(parents=True)

    monkeypatch.setattr(workflow, "prepare_source", prepare_mock)
    created = []

    async def create_project_mock(**kwargs):
        created.append(kwargs)
        return {"project_id": "project-from-manager"}

    monkeypatch.setattr(workflow.project_manager, "create_project", create_project_mock)
    monkeypatch.setattr(workflow.agent_registry, "record_event", lambda *_args, **_kwargs: None)

    result = await workflow.execute_prepare(plan_id, approved=True)

    assert result["status"] == "prepared"
    assert result["project_id"] == "project-from-manager"
    assert created[0]["game_id"] == "surviving_mars"
    assert Path(result["source_path"]).is_dir()
    assert Path(result["prepared_path"]).is_dir()
    assert store.read_receipt(plan_id)["project_id"] == "project-from-manager"


@pytest.mark.asyncio
async def test_prepare_does_not_invite_duplicate_import_when_final_receipt_save_fails(
    tmp_path, monkeypatch, pipeline_store,
):
    archive_path = tmp_path / "ModContent.fpk"
    archive_path.write_bytes(_raw_archive())
    plan_id = "plan_" + "1" * 32
    manifest = _ready_manifest()
    archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    monkeypatch.setattr(workflow, "_archive_path", lambda _path: archive_path)
    monkeypatch.setattr(workflow, "_consume", lambda *_args: {
        "kind": "mars_pipeline_prepare", "execution_args": {
            "archive_path": str(archive_path), "archive_sha256": archive_hash,
            "manifest_fingerprint": store.fingerprint(manifest), "approved_ids": ["1"],
            "name": "Mars mod",
        },
    })
    monkeypatch.setattr(workflow, "extract_archive", lambda _archive, destination, **_kwargs: (
        destination.mkdir(parents=True) or {"archive_sha256": archive_hash, "files": []}
    ))
    monkeypatch.setattr(workflow, "analyze_source", lambda *_args: manifest)
    monkeypatch.setattr(workflow, "prepare_source", lambda _src, dst, *_args, **_kwargs: dst.mkdir())
    created = []

    async def create_project(**kwargs):
        created.append(kwargs)
        return {"project_id": "project-created"}

    monkeypatch.setattr(workflow.project_manager, "create_project", create_project)
    save_calls = []

    def save_receipt(_run_id, _receipt):
        save_calls.append(True)
        if len(save_calls) == 2:
            raise OSError("receipt storage unavailable")

    monkeypatch.setattr(store, "save_receipt", save_receipt)

    result = await workflow.execute_prepare(plan_id, approved=True)

    assert result["status"] == "persistence_incomplete"
    assert result["project_id"] == "project-created"
    assert "Do not repeat" in result["warnings"][0]
    assert len(created) == 1


@pytest.mark.asyncio
async def test_delivery_returns_created_package_when_receipt_persistence_fails(
    tmp_path, monkeypatch, pipeline_store,
):
    project_id, run_id = "project-1", "plan_" + "2" * 32
    plan_id = "plan_" + "3" * 32
    receipt = {"run_id": run_id, "source_path": ".", "prepared_path": ".",
               "manifest": {"entries": {}}, "deliveries": []}
    monkeypatch.setattr(workflow_delivery, "_context", lambda _project_id: _async_value(
        {"source_path": "."}, receipt,
    ))
    monkeypatch.setattr(workflow_delivery, "_consume", lambda *_args: {
        "kind": "mars_pipeline_delivery", "project_id": project_id,
        "execution_args": {"run_id": run_id, "mode": "source_copy", "outputs": [],
                           "fingerprint": "preview-hash"},
    })
    monkeypatch.setattr(workflow_delivery, "_inspect", lambda *_args: (
        {"fingerprint": "preview-hash", "status": "ready", "blockers": []}, {},
    ))
    from scripts.core.mars_pipeline import delivery

    def build(_source, _manifest, _translations, destination, _mode, *, expected_fingerprint):
        destination.mkdir(parents=True)
        return {"package_path": str(destination), "fingerprint": expected_fingerprint}

    monkeypatch.setattr(delivery, "build_delivery", build)
    monkeypatch.setattr(store, "read_receipt", lambda _run_id: receipt)
    monkeypatch.setattr(store, "save_receipt", lambda *_args: (_ for _ in ()).throw(
        OSError("receipt storage unavailable"),
    ))

    result = await workflow_delivery.execute_delivery(project_id, plan_id, approved=True)

    assert Path(result["package_path"]).is_dir()
    assert result["receipt_saved"] is False
    assert "Do not repeat" in result["warnings"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "record,code",
    [
        ({"kind": "mars_pipeline_prepare", "project_id": "project-1"}, "invalid_plan"),
        ({"kind": "mars_pipeline_delivery", "project_id": "project-other"}, "invalid_plan"),
    ],
)
async def test_delivery_rejects_wrong_kind_or_project_and_releases_plan(
    record, code, monkeypatch,
):
    released = []
    monkeypatch.setattr(workflow_delivery, "_context", lambda _project_id: _async_value(
        {"source_path": "."}, {"run_id": "plan_" + "5" * 32},
    ))
    monkeypatch.setattr(workflow_delivery, "_consume", lambda *_args: record)
    monkeypatch.setattr(workflow_delivery.agent_registry, "release_plan", released.append)

    with pytest.raises(PackageWorkflowError) as caught:
        await workflow_delivery.execute_delivery("project-1", "plan_" + "6" * 32, approved=True)

    assert caught.value.code == code
    assert released == ["plan_" + "6" * 32]


async def _async_value(*values):
    return values


async def _async_one(value):
    return value


@pytest.mark.asyncio
async def test_delivery_context_requires_a_matching_prepared_receipt(tmp_path, monkeypatch):
    source, prepared = tmp_path / "source", tmp_path / "prepared"
    source.mkdir()
    prepared.mkdir()
    monkeypatch.setattr(workflow_delivery, "_project", lambda _project_id: _async_one(
        {"source_path": str(source)},
    ))
    monkeypatch.setattr(store, "project_receipt", lambda _project_id: {
        "run_id": "plan_" + "7" * 32, "prepared_path": str(prepared),
    })

    with pytest.raises(PackageWorkflowError) as caught:
        await workflow_delivery._context("project-1")

    assert caught.value.code == "project_source_changed"


def test_delivery_rejects_translation_output_not_owned_by_project(monkeypatch):
    project = {"id": "project-1", "source_path": "."}
    monkeypatch.setattr(workflow_delivery, "_outputs", lambda _project: [{
        "output_folder_name": "zh-CN-Loc", "language_code": "zh-CN",
    }])
    monkeypatch.setattr(workflow_delivery, "_select_output",
                        lambda *_args: pytest.fail("unowned output must be rejected before selection"))

    with pytest.raises(ValueError, match="language"):
        workflow_delivery._read_translations(
            project, {"entries": {}},
            [{"output_folder_name": "external-Loc", "language_code": "zh-CN"}],
        )


@pytest.mark.asyncio
async def test_source_copy_delivery_output_stays_owned_by_preparation_run(
    tmp_path, monkeypatch, pipeline_store,
):
    project_id, run_id = "project-1", "plan_" + "8" * 32
    plan_id = "plan_" + "9" * 32
    source, prepared = tmp_path / "source", tmp_path / "prepared"
    source.mkdir()
    prepared.mkdir()
    receipt = {"run_id": run_id, "source_path": str(source),
               "prepared_path": str(prepared), "manifest": {"entries": {}}}
    monkeypatch.setattr(workflow_delivery, "_context", lambda _project_id: _async_value(
        {"source_path": str(prepared)}, receipt,
    ))
    monkeypatch.setattr(workflow_delivery, "_consume", lambda *_args: {
        "kind": "mars_pipeline_delivery", "project_id": project_id,
        "execution_args": {"run_id": run_id, "mode": "source_copy", "outputs": [],
                           "fingerprint": "preview-hash"},
    })
    monkeypatch.setattr(workflow_delivery, "_inspect", lambda *_args: (
        {"fingerprint": "preview-hash", "status": "ready", "blockers": []},
        {"zh-CN": {"1": "文本"}},
    ))
    destinations = []

    def build(_source, _manifest, _translations, destination, mode, *, expected_fingerprint):
        destinations.append((destination, mode, expected_fingerprint))
        destination.mkdir(parents=True)
        (destination / "receipt.txt").write_text("local", encoding="utf-8")
        return {"package_path": str(destination), "fingerprint": expected_fingerprint}

    from scripts.core.mars_pipeline import delivery

    monkeypatch.setattr(delivery, "build_delivery", build)
    monkeypatch.setattr(workflow_delivery.agent_registry, "record_event", lambda *_args, **_kwargs: None)
    saved = []
    monkeypatch.setattr(store, "save_receipt", lambda _run_id, value: saved.append(value.copy()))
    monkeypatch.setattr(store, "read_receipt", lambda _run_id: receipt)

    result = await workflow_delivery.execute_delivery(project_id, plan_id, approved=True)

    expected_root = store.run_path(run_id) / "deliveries" / plan_id
    assert destinations == [(expected_root, "source_copy", "preview-hash")]
    assert (expected_root / "receipt.txt").read_text(encoding="utf-8") == "local"
    assert result["package_path"] == str(expected_root)
    assert saved[-1]["deliveries"][-1]["plan_id"] == plan_id
    assert saved[-1]["deliveries"][-1]["mode"] == "source_copy"


@pytest.mark.asyncio
async def test_delivery_stale_fingerprint_does_not_build_or_persist_output(monkeypatch):
    project_id, run_id, plan_id = "project-1", "plan_" + "a" * 32, "plan_" + "b" * 32
    receipt = {"run_id": run_id, "source_path": ".", "prepared_path": ".",
               "manifest": {"entries": {}}, "deliveries": []}
    monkeypatch.setattr(workflow_delivery, "_context", lambda _project_id: _async_value(
        {"source_path": "."}, receipt,
    ))
    monkeypatch.setattr(workflow_delivery, "_consume", lambda *_args: {
        "kind": "mars_pipeline_delivery", "project_id": project_id,
        "execution_args": {"run_id": run_id, "mode": "source_copy", "outputs": [],
                           "fingerprint": "preview-hash"},
    })
    monkeypatch.setattr(workflow_delivery, "_inspect", lambda *_args: (
        {"fingerprint": "changed-after-preview", "status": "ready", "blockers": []}, {},
    ))
    released = []
    persisted = []
    monkeypatch.setattr(workflow_delivery.agent_registry, "release_plan", released.append)
    monkeypatch.setattr(store, "save_receipt", lambda *_args: persisted.append(True))

    with pytest.raises(ValueError, match="changed; make a fresh preview"):
        await workflow_delivery.execute_delivery(project_id, plan_id, approved=True)

    assert released == [plan_id]
    assert persisted == []
    assert receipt["deliveries"] == []


def test_run_path_rejects_non_plan_receipt_names(pipeline_store):
    with pytest.raises(ValueError, match="Invalid pipeline run identity"):
        store.run_path("../outside")


def test_pipeline_store_rejects_redirected_appdata_root(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    redirected = tmp_path / "app-data"
    try:
        redirected.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    monkeypatch.setattr(store, "APP_DATA_DIR", redirected)

    with pytest.raises(ValueError, match="links or junctions"):
        store.root()


def test_project_receipt_returns_only_prepared_receipts_owned_by_project(pipeline_store):
    runs = pipeline_store / "runs"
    records = [
        ("plan_" + "c" * 32, {"project_id": "project-1", "status": "failed"}),
        ("plan_" + "d" * 32, {"project_id": "another-project", "status": "prepared"}),
        ("plan_" + "e" * 32, {"project_id": "project-1", "status": "prepared", "run_id": "owned"}),
    ]
    for run_id, receipt in records:
        run = runs / run_id
        run.mkdir(parents=True)
        (run / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

    assert store.project_receipt("project-1")["run_id"] == "owned"


def test_delivery_destination_must_remain_outside_source_mod(tmp_path):
    from scripts.core.mars_pipeline.delivery import MarsDeliveryError, _assert_destination

    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(MarsDeliveryError, match="inside the source Mod"):
        _assert_destination(source / "deliveries" / "output", source)


def test_export_api_accepts_source_copy_mode_for_real_mod_delivery():
    request = DeliveryPlan.model_validate({
        "mode": "source_copy",
        "outputs": [{"output_folder_name": "zh-CN-Loc", "language_code": "zh-CN"}],
    })
    assert request.mode == "source_copy"


def test_delivery_inspection_uses_server_binding_not_request(monkeypatch):
    from scripts.core.mars_pipeline import delivery

    binding = {"status": "bound", "revision": 1, "steam_id": "3807689989"}
    receipt = {"project_id": "project-1", "source_path": ".", "manifest": {}}
    monkeypatch.setattr(workflow_delivery, "_read_translations", lambda *_args: {})
    seen = []
    monkeypatch.setattr(workflow_delivery, "get_publication_binding", lambda project_id, current: (
        seen.append((project_id, current)) or binding
    ))
    passed = []
    monkeypatch.setattr(delivery, "inspect_delivery", lambda *_args, **kwargs: (
        passed.append(kwargs) or {"fingerprint": "test"}
    ))
    inspection, _ = workflow_delivery._inspect({}, receipt, {
        "mode": "source_copy", "outputs": [], "publication_binding": {"steam_id": "3679917456"},
    })
    assert seen == [("project-1", receipt)]
    assert passed == [{"publication_binding": binding}]
    assert inspection["publication_binding"] == binding


def test_corrupt_binding_blocks_inspection_without_fallback(monkeypatch):
    from scripts.core.mars_pipeline import delivery
    from scripts.core.mars_pipeline.publication_identity import PublicationIdentityError

    def corrupt(*_args):
        raise PublicationIdentityError("Publication binding is corrupt")

    monkeypatch.setattr(workflow_delivery, "_read_translations", lambda *_args: {})
    monkeypatch.setattr(workflow_delivery, "get_publication_binding", corrupt)
    monkeypatch.setattr(delivery, "inspect_delivery", lambda *_args, **_kwargs: pytest.fail("must fail closed"))
    with pytest.raises(PublicationIdentityError, match="corrupt"):
        workflow_delivery._inspect({}, {"project_id": "project-1", "manifest": {}}, {
            "mode": "source_copy", "outputs": [],
        })
