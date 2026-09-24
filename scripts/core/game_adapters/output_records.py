"""Read package provenance for validation and source-to-target proofreading."""
import json
from pathlib import Path

from .workflow_bridge import MANIFEST, safe_output


def output_record(path: str | Path) -> tuple[Path | None, dict]:
    target = Path(path).resolve()
    for parent in target.parents:
        candidate = parent / MANIFEST
        if not candidate.is_file():
            continue
        manifest = json.loads(candidate.read_text(encoding="utf-8"))
        record = manifest.get("files", {}).get(target.relative_to(parent).as_posix())
        if record is not None:
            return parent, record
    return None, {}


def source_values(path: str | Path) -> dict[str, str]:
    _, record = output_record(path)
    return {entry["key"]: entry["source"] for entry in record.get("entries", [])}


def output_files(root: str | Path, language: str) -> list[str]:
    files = []
    for path in Path(root).rglob(MANIFEST):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for relative, record in manifest.get("files", {}).items():
            if record.get("language") == language:
                target = safe_output(path.parent, relative)
                if target.is_file():
                    files.append(str(target))
    return sorted(set(files))
