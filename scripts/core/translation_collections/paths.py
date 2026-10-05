"""Path guards shared by translation collection packaging modes."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import stat


def safe_relative(value: str) -> tuple[str, ...]:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe package path: {value}")
    if any("\\" in part or ":" in part or part.endswith((".", " ")) for part in path.parts):
        raise ValueError(f"Unsafe package path: {value}")
    return path.parts


def is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )
