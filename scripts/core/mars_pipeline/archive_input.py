"""Classify a user-selected Mod folder without extracting or changing it."""
from pathlib import Path

from scripts.core.copilot.workflow import _resolve_allowed_mod_folder


def inspect_input(raw: str) -> dict:
    path = Path(raw).absolute()
    if path.is_dir():
        allowed = _resolve_allowed_mod_folder(str(path))
        if allowed != path or path.resolve() != path or path.is_symlink():
            raise ValueError("Mod folder cannot traverse redirected directories")
        archives = sorted(item for item in path.iterdir() if item.suffix.lower() == ".fpk")
        if not archives:
            return {"kind": "editable_folder", "archive_path": None}
        if len(archives) != 1:
            raise ValueError("This folder contains multiple .fpk archives. Choose the intended file in Advanced options.")
        path = archives[0]
    allowed_parent = _resolve_allowed_mod_folder(str(path.parent))
    if path.parent != allowed_parent or path.resolve() != path or path.is_symlink():
        raise ValueError("Archive path cannot traverse redirected directories")
    if path.suffix.lower() != ".fpk" or not path.is_file():
        raise ValueError("Choose a Mod folder containing ModContent.fpk or an editable localization folder.")
    return {"kind": "archive", "archive_path": str(path)}
