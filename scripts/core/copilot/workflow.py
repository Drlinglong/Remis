"""Approval-gated Copilot workflows backed by Remis domain services."""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.shared.services import project_manager
from scripts.app_settings import API_PROVIDERS, APP_DATA_DIR, PROJECT_ROOT
from scripts.core.copilot.provider_readiness import (
    check_provider_readiness,
)

PLAN_TTL_SECONDS = 30 * 60
MAX_SCAN_FILES = 5000
LOCALIZATION_SUFFIXES = {".yml", ".yaml", ".json", ".csv"}


@dataclass
class StoredPlan:
    payload: dict[str, Any]
    expires_at: float
    executed: bool = False


_plans: dict[str, StoredPlan] = {}
_plans_lock = threading.Lock()


def _resolve_allowed_mod_folder(folder_path: str) -> Path:
    normalized = os.path.normcase(
        os.path.realpath(os.path.expanduser(folder_path))
    )
    bundled_demo_root = os.path.normcase(
        os.path.realpath(os.path.join(APP_DATA_DIR, "demos"))
    )
    allowed_roots = {
        os.path.normcase(os.path.realpath(str(Path.home()))),
        os.path.normcase(os.path.realpath(str(PROJECT_ROOT))),
        bundled_demo_root,
    }
    configured_roots = os.environ.get("REMIS_AGENT_IMPORT_ROOTS", "")
    for configured in configured_roots.split(os.pathsep):
        if configured.strip():
            allowed_roots.add(
                os.path.normcase(
                    os.path.realpath(os.path.expanduser(configured.strip()))
                )
            )
    for drive_letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        for relative_root in (
            r"SteamLibrary\steamapps\workshop\content",
            r"Steam\steamapps\workshop\content",
            r"Program Files (x86)\Steam\steamapps\workshop\content",
        ):
            allowed_roots.add(
                os.path.normcase(
                    os.path.realpath(f"{drive_letter}:\\{relative_root}")
                )
            )

    matched_root: str | None = None
    for allowed_root in sorted(allowed_roots, key=len, reverse=True):
        allowed_prefix = allowed_root.rstrip("\\/") + os.sep
        if normalized == allowed_root or normalized.startswith(allowed_prefix):
            matched_root = allowed_root
            break
    if matched_root is None:
        raise ValueError(
            "Mod folder is outside the allowed local import roots"
        )

    protected_roots = {
        os.path.normcase(
            os.path.realpath(os.environ.get("WINDIR", "C:/Windows"))
        ),
    }
    for name in ("ProgramFiles", "ProgramFiles(x86)", "APPDATA"):
        value = os.environ.get(name)
        if value:
            protected_roots.add(os.path.normcase(os.path.realpath(value)))
    for protected_root in protected_roots:
        protected_prefix = protected_root.rstrip("\\/") + os.sep
        inside_bundled_demos = normalized.startswith(
            bundled_demo_root.rstrip("\\/") + os.sep
        )
        if not inside_bundled_demos and (
            normalized == protected_root or normalized.startswith(protected_prefix)
        ):
            raise ValueError("Mod folder is inside a protected system root")

    if normalized == matched_root or os.path.dirname(normalized) == normalized:
        raise ValueError("Select a specific mod folder")

    relative_parts = Path(os.path.relpath(normalized, matched_root)).parts
    current = Path(matched_root)
    for component in relative_parts:
        if (
            component in {"", ".", ".."}
            or os.path.basename(component) != component
        ):
            raise ValueError("Mod folder path is invalid")
        try:
            with os.scandir(current) as entries:
                match = next(
                    (
                        entry
                        for entry in entries
                        if os.path.normcase(entry.name)
                        == os.path.normcase(component)
                    ),
                    None,
                )
        except PermissionError as exc:
            raise PermissionError(
                f"Permission denied while inspecting mod folder: {current}"
            ) from exc
        except OSError as exc:
            raise ValueError("Mod folder does not exist") from exc
        if match is None:
            raise ValueError("Mod folder does not exist")
        current = Path(match.path)

    if not current.is_dir():
        raise ValueError("Mod folder does not exist")
    return current


def inspect_mod_folder(folder_path: str) -> dict[str, Any]:
    """Read only names and basic metadata under an allowed local mod folder."""
    root = _resolve_allowed_mod_folder(folder_path)

    total_files = 0
    localization_files = 0
    sample_paths: list[str] = []
    metadata_files: list[str] = []
    truncated = False
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        for name in files:
            total_files += 1
            path = Path(current_root, name)
            rel = path.relative_to(root).as_posix()
            lower_name = name.lower()
            if lower_name in {"descriptor.mod", "metadata.json"}:
                metadata_files.append(rel)
            if path.suffix.lower() in LOCALIZATION_SUFFIXES and any(
                part.lower() in {"localisation", "localization"}
                for part in path.parts
            ):
                localization_files += 1
                if len(sample_paths) < 8:
                    sample_paths.append(rel)
            if total_files >= MAX_SCAN_FILES:
                truncated = True
                break
        if truncated:
            break

    return {
        "folder_path": str(root),
        "folder_name": root.name,
        "total_files_scanned": total_files,
        "localization_file_count": localization_files,
        "localization_samples": sample_paths,
        "metadata_files": metadata_files[:8],
        "scan_truncated": truncated,
        "read_only": True,
    }


def create_localization_plan(
    *,
    folder_path: str,
    project_name: str,
    game_id: str,
    source_language: str,
    import_mode: str,
    target_language: str = "zh-CN",
    api_provider: str = "lm_studio",
    model: str = "google/gemma-4-31b-qat",
    batch_size_limit: int | None = 10,
    concurrency_limit: int | None = 1,
    rpm_limit: int | None = 40,
    use_resume: bool = True,
    use_main_glossary: bool = True,
    embedded_workshop_enabled: bool = True,
) -> dict[str, Any]:
    inspection = inspect_mod_folder(folder_path)
    name = project_name.strip()
    if not name:
        raise ValueError("Project name is required")
    if import_mode not in {"copy", "reference"}:
        raise ValueError("Import mode must be copy or reference")
    if target_language == source_language:
        raise ValueError("Target language must differ from the source language")
    if api_provider not in API_PROVIDERS:
        raise ValueError(f"Unknown API provider: {api_provider}")
    if not model.strip():
        raise ValueError("Model is required")

    plan_id = str(uuid.uuid4())
    payload = {
        "plan_id": plan_id,
        "workflow_type": "localize_mod_v1",
        "status": "awaiting_approval",
        "title": f"创建汉化项目：{name}",
        "summary": "只读检查已完成。批准后由 Remis 创建项目，并按已确认参数立即启动初次翻译。",
        "inspection": inspection,
        "steps": [
            {
                "id": "inspect_mod_folder",
                "label": "只读检查 Mod 文件夹",
                "status": "completed",
                "effect": "read_only",
            },
            {
                "id": "create_project",
                "label": "创建 Remis 项目",
                "status": "pending_approval",
                "effect": "writes_database_and_may_copy_files",
            },
            {
                "id": "open_initial_translation",
                "label": f"启动 {source_language} → {target_language} 初次翻译",
                "status": "pending_approval",
                "effect": "writes_translation_output_and_may_use_paid_api",
            },
        ],
        "execution_args": {
            "name": name,
            "folder_path": inspection["folder_path"],
            "game_id": game_id,
            "source_language": source_language,
            "import_mode": import_mode,
        },
        "translation_args": {
            "target_lang_codes": [target_language],
            "api_provider": api_provider,
            "model": model.strip(),
            "batch_size_limit": batch_size_limit,
            "concurrency_limit": concurrency_limit,
            "rpm_limit": rpm_limit,
            "use_resume": use_resume,
            "use_main_glossary": use_main_glossary,
            "embedded_workshop_enabled": embedded_workshop_enabled,
        },
        "requires_approval": True,
        "expires_in_seconds": PLAN_TTL_SECONDS,
    }
    with _plans_lock:
        _plans[plan_id] = StoredPlan(payload=payload, expires_at=time.time() + PLAN_TTL_SECONDS)
    return payload


async def approve_and_execute_plan(plan_id: str) -> dict[str, Any]:
    with _plans_lock:
        stored = _plans.get(plan_id)
        if not stored:
            raise KeyError("Workflow plan was not found or the app restarted")
        if stored.expires_at < time.time():
            _plans.pop(plan_id, None)
            raise TimeoutError("Workflow plan expired; inspect the folder again")
        if stored.executed:
            raise RuntimeError("Workflow plan has already been executed")
        # Reserve before awaiting so double clicks cannot execute twice.
        stored.executed = True
        args = dict(stored.payload["execution_args"])

    try:
        project = await project_manager.create_project(**args)
    except Exception:
        with _plans_lock:
            stored.executed = False
        raise

    return {
        "plan_id": plan_id,
        "status": "completed",
        "project": project,
        "next_action": {
            "action": "open_initial_translation",
            "label": "进入初次翻译",
            "args": {"project_id": project.get("project_id")},
        },
    }


async def create_translation_plan(
    *,
    project_id: str,
    target_lang_codes: list[str],
    api_provider: str,
    model: str,
    batch_size_limit: int | None = None,
    concurrency_limit: int | None = None,
    rpm_limit: int | None = 40,
    use_resume: bool = True,
    use_main_glossary: bool = True,
    embedded_workshop_enabled: bool = True,
) -> dict[str, Any]:
    project = await project_manager.get_project(project_id)
    if not project:
        raise ValueError("Project not found")
    files = await project_manager.get_project_files(project_id)
    source_language = str(project.get("source_language") or "en")
    targets = [str(code).strip() for code in target_lang_codes if str(code).strip()]
    if not targets:
        raise ValueError("At least one target language is required")
    if source_language in targets:
        raise ValueError("Target language must differ from the project source language")
    if api_provider not in API_PROVIDERS:
        raise ValueError(f"Unknown API provider: {api_provider}")
    if not model.strip():
        raise ValueError("Model is required")
    for label, value in {
        "batch_size_limit": batch_size_limit,
        "concurrency_limit": concurrency_limit,
        "rpm_limit": rpm_limit,
    }.items():
        if value is not None and value < 1:
            raise ValueError(f"{label} must be at least 1")

    args = {
        "project_id": project_id,
        "source_lang_code": source_language,
        "target_lang_codes": targets,
        "api_provider": api_provider,
        "model": model.strip(),
        "batch_size_limit": batch_size_limit,
        "concurrency_limit": concurrency_limit,
        "rpm_limit": rpm_limit,
        "mod_context": "",
        "selected_glossary_ids": [],
        "use_main_glossary": use_main_glossary,
        "clean_source": False,
        "use_resume": use_resume,
        "embedded_workshop": {
            "enabled": embedded_workshop_enabled,
            "follow_primary_settings": True,
            "batch_size_limit": batch_size_limit,
            "concurrency_limit": concurrency_limit,
            "rpm_limit": rpm_limit,
        },
    }
    plan_id = str(uuid.uuid4())
    payload = {
        "plan_id": plan_id,
        "workflow_type": "initial_translation_v1",
        "status": "awaiting_approval",
        "title": f"启动初次翻译：{project.get('name')}",
        "summary": "批准后将创建后台翻译任务并开始写入翻译输出；源 Mod 文件不会由 Agent 直接修改。",
        "inspection": {
            "project_id": project_id,
            "project_name": project.get("name"),
            "source_path": project.get("source_path"),
            "source_language": source_language,
            "project_file_count": len(files),
            "read_only": True,
        },
        "steps": [
            {"id": "inspect_project", "label": "只读检查项目与文件统计", "status": "completed", "effect": "read_only"},
            {"id": "start_translation", "label": "创建并启动初次翻译任务", "status": "pending_approval", "effect": "writes_translation_output"},
            {"id": "monitor_task", "label": "监控翻译进度与错误", "status": "after_execution", "effect": "read_only"},
        ],
        "execution_args": args,
        "requires_approval": True,
        "expires_in_seconds": PLAN_TTL_SECONDS,
    }
    with _plans_lock:
        _plans[plan_id] = StoredPlan(payload=payload, expires_at=time.time() + PLAN_TTL_SECONDS)
    return payload


def reserve_translation_plan(plan_id: str) -> dict[str, Any]:
    """Atomically reserve an approved translation plan for the existing task runner."""
    with _plans_lock:
        stored = _plans.get(plan_id)
        if not stored:
            raise KeyError("Workflow plan was not found or the app restarted")
        if stored.expires_at < time.time():
            _plans.pop(plan_id, None)
            raise TimeoutError("Workflow plan expired; inspect the project again")
        if stored.payload.get("workflow_type") != "initial_translation_v1":
            raise ValueError("Workflow plan is not an initial translation plan")
        if stored.executed:
            raise RuntimeError("Workflow plan has already been executed")
        stored.executed = True
        return dict(stored.payload["execution_args"])


def release_plan_reservation(plan_id: str) -> None:
    with _plans_lock:
        stored = _plans.get(plan_id)
        if stored:
            stored.executed = False


def get_localization_translation_args(plan_id: str) -> dict[str, Any]:
    """Return the server-owned translation parameters attached to an approved plan."""
    with _plans_lock:
        stored = _plans.get(plan_id)
        if not stored:
            raise KeyError("Workflow plan was not found or the app restarted")
        if stored.payload.get("workflow_type") != "localize_mod_v1":
            raise ValueError("Workflow plan is not a localization plan")
        return dict(stored.payload.get("translation_args") or {})


async def ensure_localization_provider_ready(plan_id: str) -> dict[str, Any] | None:
    """Run provider checks immediately before a guided project is created.

    The optional ``None`` result is intentional for compatibility with callers
    that replace the project approval function in tests. Real localization
    plans are always checked; no project write happens in this function.
    """
    with _plans_lock:
        stored = _plans.get(plan_id)
        if not stored:
            return None
        if stored.payload.get("workflow_type") != "localize_mod_v1":
            raise ValueError("Workflow plan is not a localization plan")
        translation_args = dict(stored.payload.get("translation_args") or {})
    readiness = await check_provider_readiness(
        str(translation_args.get("api_provider") or ""),
        str(translation_args.get("model") or ""),
    )
    return readiness


async def ensure_translation_provider_ready(plan_id: str) -> dict[str, Any]:
    """Fail closed on external readiness before reserving a translation plan."""
    with _plans_lock:
        stored = _plans.get(plan_id)
        if not stored:
            raise KeyError("Workflow plan was not found or the app restarted")
        if stored.expires_at < time.time():
            _plans.pop(plan_id, None)
            raise TimeoutError("Workflow plan expired; inspect the project again")
        if stored.payload.get("workflow_type") != "initial_translation_v1":
            raise ValueError("Workflow plan is not an initial translation plan")
        if stored.executed:
            raise RuntimeError("Workflow plan has already been executed")
        args = dict(stored.payload.get("execution_args") or {})
    return await check_provider_readiness(
        str(args.get("api_provider") or ""),
        str(args.get("model") or ""),
    )
