from pathlib import Path


THUMBNAIL_CANDIDATES = (
    "thumbnail.png",
    "thumbnail.jpg",
    "thumbnail.jpeg",
    "thumbnail.webp",
    ".metadata/thumbnail.png",
)


def find_project_thumbnail(source_path: str | None) -> Path:
    """Find a supported thumbnail contained by a project's source root."""
    if not source_path:
        raise LookupError("Bound project source path is unavailable")
    try:
        source_root = Path(source_path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LookupError("Bound project source path is unavailable") from exc
    if not source_root.is_dir():
        raise LookupError("Bound project source path is unavailable")

    for relative_path in THUMBNAIL_CANDIDATES:
        try:
            candidate = (source_root / relative_path).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if candidate.is_relative_to(source_root) and candidate.is_file():
            return candidate
    raise LookupError("Project thumbnail not found")
