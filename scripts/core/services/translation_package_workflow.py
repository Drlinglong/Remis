"""Project-owned, approval-gated local translation package exports."""
from __future__ import annotations

import hashlib
import asyncio
from pathlib import Path
import re

from scripts.app_settings import APP_DATA_DIR, LANGUAGES, resolve_path
from scripts.core.agent_service import agent_registry
from scripts.core.services import mars_translation_package as mars
from scripts.shared.services import project_manager


class PackageWorkflowError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code = status, code


async def _project(project_id: str) -> dict:
    project = await project_manager.get_project(project_id)
    if not project:
        raise PackageWorkflowError(404, "project_not_found", "Project not found")
    if project.get("game_id") != "surviving_mars":
        raise PackageWorkflowError(409, "unsupported_game", "This package exporter supports Surviving Mars CSV projects.")
    return project


def _outputs(project: dict) -> list[dict]:
    sidecar = project_manager._read_project_sidecar(project["source_path"])
    config = sidecar.get("config") or {}
    if not isinstance(config, dict):
        return []
    paths = config.get("translation_dirs") or []
    if not isinstance(paths, list):
        return []
    outputs = {}
    for raw in paths:
        if not isinstance(raw, str) or not raw:
            continue
        path = Path(resolve_path(raw)).absolute()
        if not path.is_dir():
            continue
        language = next((code for code in mars.LANGUAGE_NAMES if path.name.startswith(code + "-")), "")
        outputs[str(path)] = {"output_folder_name": path.name, "path": str(path), "language_code": language}
    return list(outputs.values())


def _select_output(project: dict, name: str) -> Path:
    if not name or name in {".", ".."} or any(char in name for char in "/\\"):
        raise PackageWorkflowError(400, "invalid_output_folder", "Select one project-owned translation folder.")
    matches = [item for item in _outputs(project) if item["output_folder_name"] == name]
    if len(matches) != 1:
        raise PackageWorkflowError(409, "output_selection_required", "The output is missing, ambiguous, or not associated with this project.")
    return Path(matches[0]["path"])


def _language_options() -> list[dict]:
    names = {value["code"]: value.get("name", value["code"]) for value in LANGUAGES.values()}
    return [{"code": code, "name": names.get(code, code), "game_language": token}
            for code, token in mars.LANGUAGE_NAMES.items()]


async def package_options(project_id: str) -> dict:
    project = await _project(project_id)
    warnings = []
    try:
        metadata = mars.read_source_metadata(Path(project["source_path"]))
    except (ValueError, OSError) as exc:
        metadata = {}
        warnings.append(str(exc))
    return {
        "supported": True, "game_id": "surviving_mars", "project_id": project_id,
        "source_mod": {"id": metadata.get("id") or "", "title": metadata.get("title") or ""},
        "translation_outputs": _outputs(project), "languages": _language_options(),
        "warnings": warnings,
        "limitations": ["Exports a local translation-only Mod; does not install, publish, or build FPK archives.",
                        "The original Mod remains required. Hard-coded Untranslated strings are outside CSV coverage."],
        "runtime_verified": False,
    }


def _inspect(project: dict, output: Path, request: dict) -> dict:
    output_language = next((code for code in mars.LANGUAGE_NAMES if output.name.startswith(code + "-")), None)
    if output_language and output_language != request["target_language"]:
        raise PackageWorkflowError(422, "language_mismatch", "Choose the language belonging to this translation output.")
    return mars.inspect_package_inputs(
        Path(project["source_path"]), output, request["target_language"],
        source_mod_id=request.get("source_mod_id"),
        source_mod_title=request.get("source_mod_title"), author=request.get("author"),
    )


async def plan_package(project_id: str, request: dict) -> dict:
    project = await _project(project_id)
    output = _select_output(project, request["output_folder_name"])
    inspection = await asyncio.to_thread(_inspect, project, output, request)
    record = agent_registry.create_plan(
        project_id=project_id, kind="surviving_mars_translation_package", dry_run=False,
        execution_args={**request, "source_root": str(Path(project["source_path"]).absolute()),
                        "translation_root": str(output), "fingerprint": inspection["fingerprint"]},
        inspection=inspection,
        summary="Generate a local translation-only Mod with a required original-Mod dependency.",
    )
    return {**inspection, "plan_id": record["plan_id"], "project_id": project_id,
            "summary": record["summary"], "expires_at": record["expires_at"],
            "requires_approval": True, "runtime_verified": False,
            "risk": {"writes_output": True, "may_use_paid_api": False,
                     "overwrites_existing_output": False, "exports_to_game_directory": False},
            "allowed_actions": ["approve_package"]}


def _consume(plan_id: str, approved: bool) -> dict:
    if not approved:
        raise PackageWorkflowError(409, "approval_required", "Approve the reviewed package plan before generating files.")
    try:
        return agent_registry.consume_plan(plan_id, approved=True)
    except KeyError as exc:
        raise PackageWorkflowError(404, "plan_not_found", "Package plan not found") from exc
    except (TimeoutError, RuntimeError) as exc:
        raise PackageWorkflowError(409, "stale_plan", "The plan expired or was already used. Create a new preview.") from exc


def _destination(project_id: str, plan_id: str, mod_id: str) -> Path:
    if not re.fullmatch(r"plan_[a-f0-9]{32}", plan_id) or not re.fullmatch(r"[A-Za-z0-9_-]+", mod_id):
        raise PackageWorkflowError(409, "invalid_plan", "The package plan contains an invalid output identity.")
    project_folder = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:16]
    return Path(APP_DATA_DIR) / "translation_packages" / project_folder / plan_id / mod_id


async def export_package(project_id: str, plan_id: str, approved: bool) -> dict:
    project = await _project(project_id)
    record = _consume(plan_id, approved)
    try:
        if record.get("project_id") != project_id or record.get("kind") != "surviving_mars_translation_package":
            raise PackageWorkflowError(409, "invalid_plan", "This plan does not belong to this project's package workflow.")
        request = record["execution_args"]
        output = _select_output(project, request["output_folder_name"])
        if (str(Path(project["source_path"]).absolute()) != request["source_root"]
                or str(output) != request["translation_root"]):
            raise PackageWorkflowError(409, "stale_plan", "Project paths changed. Create a new preview.")
        inspection = await asyncio.to_thread(_inspect, project, output, request)
        if inspection["fingerprint"] != request["fingerprint"]:
            raise PackageWorkflowError(409, "stale_plan", "Source or translation files changed. Create a new preview.")
        destination = _destination(project_id, plan_id, inspection["package"]["mod_id"])
        result = await asyncio.to_thread(mars.build_package,
            Path(project["source_path"]), output, request["target_language"], destination,
            source_mod_id=request.get("source_mod_id"), source_mod_title=request.get("source_mod_title"),
            author=request.get("author"), expected_fingerprint=request["fingerprint"],
        )
    except Exception:
        agent_registry.release_plan(plan_id)
        raise
    agent_registry.record_event("translation_package_generated", project_id=project_id,
                                plan_id=plan_id, package_path=result["package_path"])
    return {**result, "project_id": project_id, "plan_id": plan_id,
            "runtime_verified": False, "allowed_actions": ["inspect_local_output"]}
