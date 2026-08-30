"""Read-only workflow entity catalogue and deterministic identity resolution."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

from scripts.app_settings import PROJECTS_DB_PATH
from scripts.core.copilot.settings import list_copilot_providers


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)


def _read_projects() -> list[dict[str, str]]:
    """Return only non-secret fields needed to identify an existing project."""
    db_path = Path(PROJECTS_DB_PATH)
    if not db_path.is_file():
        return []
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=2) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            rows = connection.execute(
                "SELECT project_id, name, game_id, source_language, status "
                "FROM projects ORDER BY name, project_id"
            ).fetchall()
    except sqlite3.Error:
        return []
    return [
        {
            "project_id": str(row["project_id"]),
            "name": str(row["name"] or ""),
            "game_id": str(row["game_id"] or ""),
            "source_language": str(row["source_language"] or ""),
            "status": str(row["status"] or ""),
        }
        for row in rows
    ]


def build_workflow_entity_catalog() -> dict[str, Any]:
    """Build the bounded catalogue exposed to planning models; never include secrets or paths."""
    providers = [
        {
            "id": item["id"],
            "name": item["name"],
            "models": list(item.get("models") or [])[:100],
            "default_model": item.get("default_model") or "",
        }
        for item in list_copilot_providers()
    ]
    return {
        "projects": _read_projects()[:200],
        "providers": providers,
        "read_only": True,
        "secrets_exposed": False,
    }


def _unique_match(value: Any, items: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, Any] | None:
    wanted = _identity(value)
    if not wanted:
        return None
    matches = [item for item in items if any(_identity(item.get(field)) == wanted for field in fields)]
    return matches[0] if len(matches) == 1 else None


def _unique_model(value: Any, models: list[str]) -> str | None:
    wanted = _identity(value)
    if not wanted:
        return None
    exact = [model for model in models if _identity(model) == wanted]
    if len(exact) == 1:
        return exact[0]
    suffix = [model for model in models if _identity(model).endswith(wanted)]
    return suffix[0] if len(suffix) == 1 else None


def canonicalize_workflow_entities(
    raw_args: dict[str, Any],
    catalog: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Replace model prose with canonical IDs, failing closed on missing or ambiguous entities."""
    if not catalog:
        return dict(raw_args)
    candidate = dict(raw_args)
    projects = list(catalog.get("projects") or [])
    providers = list(catalog.get("providers") or [])

    provider = _unique_match(candidate.get("api_provider"), providers, ("id", "name"))
    if provider is None:
        return None
    model = _unique_model(candidate.get("model"), list(provider.get("models") or []))
    if model is None:
        return None
    candidate["api_provider"] = provider["id"]
    candidate["model"] = model

    if candidate.get("project_mode") != "existing":
        return candidate
    project = _unique_match(candidate.get("project_id"), projects, ("project_id",))
    if project is None:
        project = _unique_match(candidate.get("project_name"), projects, ("name",))
    if project is None:
        return None
    candidate["project_id"] = project["project_id"]
    candidate["project_name"] = project["name"]
    return candidate
