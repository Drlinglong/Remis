"""Admission boundary for the legacy path-based translation endpoint."""

from __future__ import annotations

import os
import shutil
import uuid
from typing import Any

from scripts.shared import task_state


class InvalidLegacyProjectPath(ValueError):
    """Raised before task admission when the requested source path is invalid."""


class LegacySourcePreparationError(RuntimeError):
    """Raised before task admission when the managed source copy fails."""


def prepare_legacy_translation_start(
    *,
    payload: Any,
    provider_fields: dict,
    source_dir: str,
) -> tuple[str, str]:
    project_path = str(payload.project_path)
    if not os.path.isdir(project_path):
        raise InvalidLegacyProjectPath("Invalid project path.")

    mod_name = os.path.basename(os.path.normpath(project_path))
    if not mod_name or mod_name in {".", ".."}:
        raise InvalidLegacyProjectPath("Select a specific project folder, not a filesystem root.")

    source_root = os.path.abspath(source_dir)
    source_path = os.path.abspath(os.path.join(source_root, mod_name))
    try:
        destination_root = os.path.normcase(source_root)
        destination_path = os.path.normcase(source_path)
        if (
            destination_path == destination_root
            or os.path.commonpath([destination_root, destination_path]) != destination_root
        ):
            raise InvalidLegacyProjectPath("Project folder name is not a safe managed path.")
    except ValueError as exc:
        raise InvalidLegacyProjectPath("Project folder name is not a safe managed path.") from exc

    try:
        if not payload.is_existing_source:
            if os.path.lexists(source_path):
                raise InvalidLegacyProjectPath(
                    "A managed source folder with this name already exists; choose it as the existing source or rename the imported folder."
                )
            shutil.copytree(project_path, source_path)
    except InvalidLegacyProjectPath:
        raise
    except Exception as exc:
        raise LegacySourcePreparationError("File processing failed.") from exc

    task_id = str(uuid.uuid4())
    task_state.create_task(
        task_id,
        status="starting",
        log_message=f"Using source: '{mod_name}'",
        fields={
            "kind": "initial_translation",
            "title": "Mod translation",
            "source_route": "/translation",
            **provider_fields,
        },
        require_persistence=True,
    )
    return task_id, mod_name
