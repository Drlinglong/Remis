"""Keep incremental reads inside the user-selected real source directory."""

import os
import stat
from pathlib import Path


def source_root(path: str | Path) -> Path:
    """The selected root may itself be a junction; its real target owns the scope."""
    return Path(path).expanduser().resolve()


def checked_source_path(root: Path, path: Path, *, missing_ok: bool = False) -> Path:
    """Reject redirected descendants before any resource content is opened."""
    root = source_root(root)
    candidate = path.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Incremental source path is outside the selected root: {candidate}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            if missing_ok and current == candidate:
                break
            raise
        attributes = getattr(metadata, "st_file_attributes", 0)
        if stat.S_ISLNK(metadata.st_mode) or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError(f"Linked incremental source resource is not allowed: {current}")

    try:
        candidate.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Incremental source path resolves outside the selected root: {candidate}") from exc
    return candidate


def _raise_walk_error(error: OSError) -> None:
    raise error


def walk_source_tree(root: str | Path):
    """Inspect directory links before os.walk can descend into Windows junctions."""
    root = source_root(root)
    for current, directories, files in os.walk(root, followlinks=False, onerror=_raise_walk_error):
        current_path = checked_source_path(root, Path(current))
        for directory in directories:
            checked_source_path(root, current_path / directory)
        yield str(current_path), directories, files


def validate_source_tree(root: str | Path) -> None:
    """Adapters may parse during discovery, so validate their tree before discovery."""
    root = source_root(root)
    for current, _directories, files in walk_source_tree(root):
        for filename in files:
            checked_source_path(root, Path(current) / filename)
