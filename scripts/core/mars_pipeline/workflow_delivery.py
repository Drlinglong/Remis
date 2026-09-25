"""Bind delivery previews to a prepared project and its persisted translations."""
from __future__ import annotations

import asyncio
from pathlib import Path

from scripts.core import surviving_mars_csv as csv_adapter
from scripts.core.agent_service import agent_registry
from scripts.core.mars_pipeline import workflow_store as store
from scripts.core.mars_pipeline.publication_identity import get_publication_binding
from scripts.core.services.translation_package_workflow import (
    PackageWorkflowError, _consume, _language_options, _outputs, _project, _select_output,
)


async def _context(project_id: str) -> tuple[dict, dict]:
    project = await _project(project_id)
    receipt = store.project_receipt(project_id)
    if not receipt:
        raise PackageWorkflowError(409, "source_preparation_required", "Prepare this Mod from its FPK before exporting Lua changes")
    if Path(project["source_path"]).resolve() != Path(receipt["prepared_path"]).resolve():
        raise PackageWorkflowError(409, "project_source_changed", "Project source no longer matches this preparation run")
    return project, receipt


async def options(project_id: str) -> dict:
    project = await _project(project_id)
    receipt = store.project_receipt(project_id)
    entries = receipt["manifest"]["entries"] if receipt else {}
    hardcoded_ids = {key for key, entry in entries.items() if entry.get("kind") != "existing_t"}
    approved_ids = set(receipt["manifest"].get("approved_ids", entries)) if receipt else set()
    return {"supported": bool(receipt), "project_id": project_id,
            "run_id": receipt["run_id"] if receipt else None,
            "modes": ["text_only", "source_copy"], "languages": _language_options(),
            "selected_delivery_mode": receipt.get("delivery_mode", "source_copy") if receipt else None,
            "hardcoded_entry_count": len(hardcoded_ids),
            "source_copy_requires_preparation": bool(receipt and not hardcoded_ids.issubset(approved_ids)),
            "translation_outputs": _outputs(project), "runtime_verified": False}


def _read_translations(
    project: dict, manifest: dict, selections: list[dict], mode: str = "source_copy",
) -> dict:
    translations = {}
    entries = manifest["entries"]
    required_ids = set(manifest.get("approved_ids", entries))
    if mode == "text_only":
        required_ids = {key for key in required_ids
                        if entries.get(key, {}).get("kind") == "existing_t"}
    if not selections:
        raise ValueError("Select at least one project translation output")
    for selection in selections:
        language = selection["language_code"]
        if language in translations:
            raise ValueError("Select each target language only once")
        name = selection["output_folder_name"]
        selected = next((item for item in _outputs(project) if item["output_folder_name"] == name), {})
        if selected.get("language_code") != language:
            raise ValueError("Translation output language does not match the selected target")
        folder = _select_output(project, name)
        translated = {}
        for path in sorted(folder.rglob("*.csv")):
            if path.is_symlink() or path.resolve() != path.absolute() or path.stat().st_size > 32_000_000:
                raise ValueError("Translation CSV is redirected or too large")
            try:
                document = csv_adapter.parse_file(path)
            except csv_adapter.NotSurvivingMarsCsv:
                continue
            for row in document.rows[document.header_row_index + 1:]:
                key, original, text = row[:3]
                if key not in entries:
                    raise ValueError(f"Unexpected translation ID: {key}")
                if mode == "text_only" and key not in required_ids:
                    continue
                if key in translated:
                    raise ValueError(f"Duplicate translation ID: {key}")
                if original != entries[key]["text"]:
                    raise ValueError(f"Translation source changed for ID {key}")
                if not text.strip():
                    raise ValueError(f"Translation is empty for ID {key}")
                if csv_adapter.compare_tags(original, text).is_mismatch:
                    raise ValueError(f"Translation tags changed for ID {key}")
                if csv_adapter.compare_newlines(original, text).is_mismatch:
                    raise ValueError(f"Translation line breaks changed for ID {key}")
                translated[key] = text
        missing = required_ids - set(translated)
        if missing:
            raise ValueError(f"Translation is incomplete: {len(missing)} missing IDs")
        translations[language] = translated
    return translations


def _inspect(project: dict, receipt: dict, request: dict) -> tuple[dict, dict]:
    from scripts.core.mars_pipeline.delivery import inspect_delivery
    translations = _read_translations(
        project, receipt["manifest"], request["outputs"], request.get("mode", "source_copy")
    )
    metadata_overrides = request.get("metadata_overrides")
    binding = (get_publication_binding(receipt["project_id"], receipt)
               if request["mode"] == "source_copy" else None)
    inspection = inspect_delivery(
        receipt["source_path"], receipt["manifest"], translations, request["mode"],
        **({"publication_binding": binding} if binding is not None else {}),
        **({"metadata_overrides": metadata_overrides} if metadata_overrides else {}),
    )
    if binding is not None:
        inspection["publication_binding"] = binding
    return inspection, translations


async def plan_delivery(project_id: str, request: dict) -> dict:
    project, receipt = await _context(project_id)
    inspection, _ = await asyncio.to_thread(_inspect, project, receipt, request)
    record = agent_registry.create_plan(
        project_id=project_id, kind="mars_pipeline_delivery", dry_run=False,
        execution_args={**request, "run_id": receipt["run_id"], "fingerprint": inspection["fingerprint"]},
        inspection=inspection, summary="Build a local Mars localization delivery without changing installed Mods.",
    )
    return {**inspection, "plan_id": record["plan_id"], "project_id": project_id,
            "requires_approval": True, "expires_at": record["expires_at"],
            "risk": {"may_use_paid_api": False, "overwrites_original": False,
                     "writes_output": True, "installs_to_game": False},
            "allowed_actions": ["approve_delivery"] if inspection.get("status") == "ready" else []}


async def execute_delivery(project_id: str, plan_id: str, approved: bool) -> dict:
    from scripts.core.mars_pipeline.delivery import build_delivery
    project, receipt = await _context(project_id)
    record = _consume(plan_id, approved)
    try:
        if record.get("kind") != "mars_pipeline_delivery" or record.get("project_id") != project_id:
            raise PackageWorkflowError(409, "invalid_plan", "This delivery plan belongs to another workflow or project")
        request = record["execution_args"]
        if request["run_id"] != receipt["run_id"]:
            raise ValueError("Prepared source changed; make a fresh preview")
        inspection, translations = await asyncio.to_thread(_inspect, project, receipt, request)
        if inspection["fingerprint"] != request["fingerprint"]:
            raise ValueError("Source, translations or publication binding changed; make a fresh preview")
        if inspection.get("status") != "ready":
            raise ValueError("Resolve delivery blockers before exporting")
        destination = store.run_path(receipt["run_id"]) / "deliveries" / plan_id
        build_options = {"expected_fingerprint": request["fingerprint"]}
        if request.get("metadata_overrides"):
            build_options["metadata_overrides"] = request["metadata_overrides"]
        if inspection.get("publication_binding") is not None:
            build_options["publication_binding"] = inspection["publication_binding"]
        result = await asyncio.to_thread(
            build_delivery, receipt["source_path"], receipt["manifest"], translations,
            destination, request["mode"], **build_options
        )
    except Exception:
        agent_registry.release_plan(plan_id)
        raise
    result["receipt_saved"] = False
    try:
        receipt = store.read_receipt(receipt["run_id"])
        receipt.setdefault("deliveries", []).append({"plan_id": plan_id, "mode": request["mode"], **result, "receipt_saved": True})
        store.save_receipt(receipt["run_id"], receipt)
        result["receipt_saved"] = True
        agent_registry.record_event("mars_delivery_generated", project_id=project_id, plan_id=plan_id)
    except (OSError, ValueError):
        result["warnings"] = ["The package exists at the returned path, but receipt or audit persistence failed. Do not repeat this export."]
    return {**result, "project_id": project_id, "plan_id": plan_id,
            "runtime_verified": False, "allowed_actions": ["inspect_local_output", "manual_install"]}
