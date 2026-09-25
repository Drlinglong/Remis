"""Project sidecar context used by discovery and translation workflows."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_project_sidecar(source_path: str) -> dict:
    sidecar_path = Path(source_path) / ".remis_project.json"
    if not sidecar_path.is_file():
        return {}
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read project sidecar %s: %s", sidecar_path, exc)
        return {}


def project_sidecar_context(source_path: str, project: dict) -> dict:
    sidecar = read_project_sidecar(source_path)
    config = sidecar.get("config", {}) if isinstance(sidecar.get("config"), dict) else {}
    context = {"source_language": config.get(
        "source_language", project.get("source_language", "en")
    )}
    version = config.get("game_version")
    if isinstance(version, str) and version.strip():
        context["game_version"] = version.strip()
    return context
