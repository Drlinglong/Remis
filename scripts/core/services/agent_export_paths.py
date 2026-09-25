"""Select job-owned export roots without broadening deployment authority."""
from pathlib import Path
from typing import Any, Dict, Optional


def export_candidate(
    task: Dict[str, Any],
    metadata: Dict[str, Any],
    requested_name: Optional[str],
    destination_root: Path,
    error,
) -> tuple[str, Path]:
    persisted_snapshot = metadata.get("last_snapshot") or {}
    raw_output_paths = (
        task.get("output_dirs")
        or persisted_snapshot.get("output_dirs")
        or []
    )
    output_paths = [Path(item).resolve() for item in raw_output_paths]
    destination_root = destination_root.resolve()
    candidates = {
        item.name: item for item in output_paths if item.parent == destination_root
    }
    if requested_name:
        if (
            requested_name in {".", ".."}
            or "/" in requested_name
            or "\\" in requested_name
        ):
            raise error(
                400,
                "invalid_output_folder",
                "output_folder_name must be a single folder name",
            )
        requested = candidates.get(requested_name)
        if requested is None:
            raise error(
                400,
                "unknown_output_folder",
                "The requested output folder does not belong to this job",
            )
        return requested.name, requested
    if len(candidates) != 1:
        raise error(
            409,
            "output_selection_required",
            "Select one output folder from the job before export",
        )
    candidate = next(iter(candidates.values()))
    return candidate.name, candidate
