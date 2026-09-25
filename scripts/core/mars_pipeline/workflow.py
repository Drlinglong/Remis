"""Approval-gated FPK preparation using ordinary Remis projects."""
from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile

from scripts.core.agent_service import agent_registry
from scripts.core.copilot.workflow import _resolve_allowed_mod_folder
from scripts.core.mars_pipeline import workflow_store as store
from scripts.core.mars_pipeline.prepare_source import analyze_source, prepare_source
from scripts.core.services.translation_package_workflow import PackageWorkflowError, _consume
from scripts.shared.services import project_manager
from tools.remis_fpk import extract_archive, inspect_archive


def _archive_path(raw: str) -> Path:
    path = Path(raw).absolute()
    allowed_parent = _resolve_allowed_mod_folder(str(path.parent))
    if path.parent != allowed_parent:
        raise ValueError("Archive path must use its canonical allowed parent")
    if path.suffix.lower() != ".fpk" or not path.is_file() or path.is_symlink():
        raise ValueError("Choose an existing, non-symlink .fpk Mod archive")
    if path.resolve() != path:
        raise ValueError("Archive paths cannot traverse redirected directories")
    return allowed_parent / path.name


def _previous(run_id: str | None) -> dict | None:
    if not run_id:
        return None
    receipt = store.read_receipt(run_id)
    if receipt.get("status") != "prepared":
        raise ValueError("Previous run must be a successfully prepared source")
    return receipt["manifest"]


def _inspect(request: dict) -> tuple[dict, dict]:
    path = _archive_path(request["archive_path"])
    archive = inspect_archive(path)
    with tempfile.TemporaryDirectory(prefix="inspect-", dir=store.root()) as scratch:
        source = Path(scratch) / "source"
        extract_archive(path, source, expected_sha256=archive["archive_sha256"])
        manifest = analyze_source(source, _previous(request.get("previous_run_id")))
    return archive, manifest


def _review(manifest: dict, request: dict) -> tuple[list[str], list[dict]]:
    entries = manifest["entries"]
    explicit = set(request.get("approved_ids") or [])
    unknown = explicit - set(entries)
    if unknown:
        raise ValueError("Approval contains unknown localization IDs")
    if request.get("delivery_mode") == "text_only":
        return sorted(key for key, entry in entries.items() if entry.get("kind") == "existing_t"), []
    approved = sorted(key for key, entry in entries.items()
                      if not entry.get("review_required") or key in explicit)
    pending = [{"id": key, "text": entry["text"], "reason": entry.get("review_reason"),
                "refs": entry.get("refs", [])}
               for key, entry in entries.items() if key not in approved]
    return approved, pending


async def plan_prepare(request: dict) -> dict:
    archive, manifest = await asyncio.to_thread(_inspect, request)
    approved, pending = _review(manifest, request)
    inspection = {
        "archive_sha256": archive["archive_sha256"],
        "file_count": len(archive["files"]), "entry_count": len(manifest["entries"]),
        "mod_id": manifest["mod_id"], "review_items": pending,
        "approved_ids": approved, "diagnostics": manifest.get("diagnostics", []),
        "source_fingerprint": manifest["source_fingerprint"],
        "hardcoded_entry_count": sum(entry.get("kind") != "existing_t" for entry in manifest["entries"].values()),
        "selected_entry_count": len(approved),
        "selected_delivery_mode": request.get("delivery_mode", "source_copy"),
        "recommended_delivery_mode": "source_copy" if any(entry.get("kind") != "existing_t" for entry in manifest["entries"].values()) else "text_only",
    }
    record = agent_registry.create_plan(
        project_id="", kind="mars_pipeline_prepare", dry_run=False,
        execution_args={**request, "archive_path": str(_archive_path(request["archive_path"])),
                        "archive_sha256": archive["archive_sha256"],
                        "manifest_fingerprint": store.fingerprint(manifest), "approved_ids": approved},
        inspection=inspection, summary="Extract all Mod assets and prepare a standard CSV translation project.",
    )
    return {**inspection, "plan_id": record["plan_id"], "expires_at": record["expires_at"],
            "requires_approval": True, "runtime_verified": False,
            "risk": {"may_use_paid_api": False, "writes_isolated_files": True,
                     "overwrites_original": False},
            "allowed_actions": ["approve_preparation"]}


async def execute_prepare(plan_id: str, approved: bool) -> dict:
    record = _consume(plan_id, approved)
    if record.get("kind") != "mars_pipeline_prepare":
        agent_registry.release_plan(plan_id)
        raise PackageWorkflowError(409, "invalid_plan", "This is not a Mars preparation plan")
    request = record["execution_args"]
    run = store.run_path(plan_id)
    if run.exists():
        raise PackageWorkflowError(409, "run_exists", "Preparation already has a receipt; inspect it before retrying")
    run.mkdir(parents=True)
    receipt = {"run_id": plan_id, "status": "preparing", "archive_path": request["archive_path"],
               "archive_sha256": request["archive_sha256"], "project_id": None}
    store.save_receipt(plan_id, receipt)
    try:
        source = run / "source"
        archive = await asyncio.to_thread(extract_archive, _archive_path(request["archive_path"]), source,
                                          expected_sha256=request["archive_sha256"])
        previous = _previous(request.get("previous_run_id"))
        manifest = await asyncio.to_thread(analyze_source, source, previous)
        if store.fingerprint(manifest) != request["manifest_fingerprint"]:
            raise ValueError("Source preparation changed after preview; make a fresh plan")
        # Translation output names derive from this folder name, so it must be
        # unique across runs instead of every import becoming zh-CN-prepared.
        prepared = run / f"mars-{plan_id.removeprefix('plan_')}"
        await asyncio.to_thread(prepare_source, source, prepared, previous,
                                mode="overlay", approved_ids=request["approved_ids"])
        manifest["approved_ids"] = request["approved_ids"]
        project = await project_manager.create_project(
            name=request["name"], folder_path=str(prepared), game_id="surviving_mars",
            source_language="en", import_mode="reference",
        )
        receipt.update(status="prepared", source_path=str(source), prepared_path=str(prepared),
                       project_id=str(project["project_id"]), manifest=manifest, archive=archive,
                       delivery_mode=request.get("delivery_mode", "source_copy"),
                       allowed_actions=["create_translation_plan", "inspect_delivery_options"])
        store.save_receipt(plan_id, receipt)
    except Exception as exc:
        if receipt.get("project_id"):
            receipt.update(status="persistence_incomplete", warnings=[
                "The project was created, but its pipeline receipt could not be saved. Do not repeat the import.",
            ], allowed_actions=["inspect_project"])
            return receipt
        receipt.update(status="failed", error=str(exc), allowed_actions=["inspect_run", "create_fresh_plan"])
        store.save_receipt(plan_id, receipt)
        raise
    try:
        agent_registry.record_event("mars_source_prepared", plan_id=plan_id, project_id=receipt["project_id"])
    except OSError:
        receipt["warnings"] = ["Project and receipt were saved, but the audit event could not be recorded."]
    return receipt


async def get_run(run_id: str) -> dict:
    try:
        return store.read_receipt(run_id)
    except FileNotFoundError as exc:
        raise PackageWorkflowError(404, "run_not_found", "Mars pipeline run not found") from exc
