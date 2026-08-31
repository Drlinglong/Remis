"""Allowlisted read-only tools exposed to the workflow-planning agent."""

from __future__ import annotations

import os
import sqlite3
import asyncio
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

from scripts.app_settings import API_PROVIDERS, PROJECTS_DB_PATH, config_manager, resolve_path
from scripts.routers.translation import check_checkpoint_status
from scripts.schemas.translation import CheckpointStatusRequest

MAX_FILE_SAMPLES = 12


def _readonly_connection() -> sqlite3.Connection:
    uri = f"file:{Path(PROJECTS_DB_PATH).resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _snapshot_project(project_id: str) -> dict[str, Any] | None:
    with _readonly_connection() as connection:
        row = connection.execute(
            "SELECT project_id, name, game_id, source_path, source_language, status "
            "FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["source_path"] = resolve_path(result["source_path"])
    return result


def _snapshot_files(project_id: str) -> list[dict[str, Any]]:
    with _readonly_connection() as connection:
        rows = connection.execute(
            "SELECT file_path, status, original_key_count, line_count "
            "FROM project_files WHERE project_id = ? ORDER BY file_path",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def build_workflow_read_tool_schemas() -> list[dict[str, Any]]:
    provider_ids = list(API_PROVIDERS)
    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    return [
        {"type": "function", "name": "inspect_translation_context", "description": "Read the complete bounded planning context: project, file summary, preferred provider/models, glossaries, and checkpoint.", "parameters": empty},
        {"type": "function", "name": "inspect_project", "description": "Read project metadata and aggregate file counts.", "parameters": empty},
        {"type": "function", "name": "list_project_files", "description": "Read a bounded sample and status summary of indexed project files.", "parameters": empty},
        {"type": "function", "name": "get_provider_status", "description": "Read non-secret configuration and reachability for one provider.", "parameters": {"type": "object", "properties": {"provider": {"type": "string", "enum": provider_ids}}, "required": ["provider"], "additionalProperties": False}},
        {"type": "function", "name": "list_available_models", "description": "Read configured model names for one provider; never returns keys.", "parameters": {"type": "object", "properties": {"provider": {"type": "string", "enum": provider_ids}}, "required": ["provider"], "additionalProperties": False}},
        {"type": "function", "name": "get_glossary_bindings", "description": "Read available and project-bound glossary metadata.", "parameters": empty},
        {"type": "function", "name": "get_checkpoint_status", "description": "Read resumable checkpoint status for the requested target languages.", "parameters": empty},
    ]


async def _inspect_project(project_id: str) -> dict[str, Any]:
    project = await asyncio.to_thread(_snapshot_project, project_id)
    if not project:
        raise ValueError("Project not found")
    files = await asyncio.to_thread(_snapshot_files, project_id)
    return {
        "project_id": project_id,
        "name": project.get("name"),
        "game_id": project.get("game_id"),
        "source_language": project.get("source_language"),
        "source_path_available": bool(project.get("source_path")),
        "file_count": len(files),
        "read_only": True,
    }


async def _list_project_files(project_id: str) -> dict[str, Any]:
    files = await asyncio.to_thread(_snapshot_files, project_id)
    statuses = Counter(str(item.get("status") or "unknown") for item in files)
    return {
        "total": len(files),
        "status_counts": dict(statuses),
        "sample_metrics": [
            {
                "original_key_count": item.get("original_key_count"),
                "line_count": item.get("line_count"),
            }
            for item in files[:MAX_FILE_SAMPLES]
        ],
        "sample_truncated": len(files) > MAX_FILE_SAMPLES,
        "read_only": True,
    }


def _provider_config(provider: str) -> dict[str, Any]:
    if provider not in API_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    base = dict(API_PROVIDERS[provider])
    overrides = config_manager.get_value("provider_config", {}).get(provider, {}) or {}
    return {**base, **{k: v for k, v in overrides.items() if k != "api_key"}}


async def _get_provider_snapshot(provider: str) -> dict[str, Any]:
    config = _provider_config(provider)
    base_url = str(config.get("api_url") or config.get("base_url") or "").rstrip("/")
    selected_model = config.get("selected_model") or config.get("default_model")
    result = {
        "provider": provider,
        "configured": bool(base_url or config.get("api_key_env")),
        "base_url": base_url,
        "selected_model": selected_model,
        "reachable": None,
        "secret_exposed": False,
        "read_only": True,
    }
    live_models: list[str] = []
    if provider == "lm_studio" and base_url:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{base_url}/models")
            result["reachable"] = response.ok
            if response.is_success:
                live_models = [item.get("id") for item in response.json().get("data", []) if item.get("id")]
        except (httpx.HTTPError, ValueError):
            result["reachable"] = False
    elif provider == "ollama" and base_url:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{base_url}/api/version")
            result["reachable"] = response.ok
        except httpx.HTTPError:
            result["reachable"] = False
    models = list(dict.fromkeys([
        *(config.get("available_models") or []),
        *(config.get("custom_models") or []),
    ]))
    selected = config.get("selected_model") or config.get("default_model")
    if selected and selected not in models:
        models.insert(0, selected)
    models = list(dict.fromkeys([*live_models, *models]))
    return {
        "status": result,
        "models": {"provider": provider, "selected_model": selected, "models": models[:100], "read_only": True},
    }


async def _get_provider_status(provider: str) -> dict[str, Any]:
    return (await _get_provider_snapshot(provider))["status"]


async def _list_available_models(provider: str) -> dict[str, Any]:
    return (await _get_provider_snapshot(provider))["models"]


async def _get_glossary_bindings(project_id: str) -> dict[str, Any]:
    project = await asyncio.to_thread(_snapshot_project, project_id)
    if not project:
        raise ValueError("Project not found")
    def read_glossaries():
        with _readonly_connection() as connection:
            available_rows = connection.execute(
                "SELECT glossary_id, name, is_main FROM glossaries WHERE game_id IN (?, ?)",
                (project.get("game_id"), "vic3" if project.get("game_id") == "victoria3" else project.get("game_id")),
            ).fetchall()
            bound_row = connection.execute(
                "SELECT g.glossary_id, g.name FROM project_glossary_bindings b "
                "JOIN glossaries g ON g.glossary_id = b.glossary_id WHERE b.project_id = ?",
                (project_id,),
            ).fetchone()
        return available_rows, bound_row

    available_rows, bound_row = await asyncio.to_thread(read_glossaries)
    available = [dict(row) for row in available_rows]
    return {
        "available_count": len(available),
        "main_glossary_available": any(bool(item.get("is_main")) for item in available),
        "project_glossary_bound": bound_row is not None,
        "read_only": True,
    }


def _safe_checkpoint_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep planning signals while excluding stored paths and arbitrary metadata."""
    targets = []
    for item in payload.get("targets") or []:
        if not isinstance(item, dict):
            continue
        last_file = item.get("last_completed_file")
        targets.append({
            "target_lang_code": item.get("target_lang_code"),
            "exists": bool(item.get("exists")),
            "completed_count": int(item.get("completed_count") or 0),
            "last_saved_at": item.get("last_saved_at"),
            "last_completed_file_name": os.path.basename(str(last_file)) if last_file else None,
        })
    return {
        "exists": bool(payload.get("exists")),
        "completed_count": int(payload.get("completed_count") or 0),
        "total_files_estimate": int(payload.get("total_files_estimate") or 0),
        "targets": targets,
        "read_only": True,
    }


async def execute_workflow_read_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    project_id: str,
    target_lang_codes: list[str],
    preferred_provider: str = "lm_studio",
) -> dict[str, Any]:
    if name == "inspect_translation_context":
        provider_snapshot = await _get_provider_snapshot(preferred_provider)
        return {
            "project": await _inspect_project(project_id),
            "files": await _list_project_files(project_id),
            "provider_status": provider_snapshot["status"],
            "models": provider_snapshot["models"],
            "glossaries": await _get_glossary_bindings(project_id),
            "checkpoint": await execute_workflow_read_tool(
                "get_checkpoint_status", {}, project_id=project_id,
                target_lang_codes=target_lang_codes,
                preferred_provider=preferred_provider,
            ),
            "read_only": True,
        }
    if name == "inspect_project":
        return await _inspect_project(project_id)
    if name == "list_project_files":
        return await _list_project_files(project_id)
    if name == "get_provider_status":
        return await _get_provider_status(str(arguments.get("provider") or ""))
    if name == "list_available_models":
        return await _list_available_models(str(arguments.get("provider") or ""))
    if name == "get_glossary_bindings":
        return await _get_glossary_bindings(project_id)
    if name == "get_checkpoint_status":
        project = await asyncio.to_thread(_snapshot_project, project_id)
        if not project:
            raise ValueError("Project not found")
        payload = CheckpointStatusRequest(
            project_id=project_id,
            target_lang_codes=target_lang_codes,
        )
        status = await check_checkpoint_status(payload)
        if hasattr(status, "model_dump"):
            status = status.model_dump()
        return _safe_checkpoint_summary(dict(status))
    raise ValueError(f"Tool is not allowlisted: {name}")
