"""Repair bundled path fields without rewriting user-authored sidecar text."""

import json
import logging
import os
import re
import stat
import tempfile
from pathlib import Path

logger = logging.getLogger("remis_init")
DEV_ROOT = re.compile(r"^[A-Za-z]:/[^\n]*?V3_Mod_Localization_Factory(?=/|$)", re.IGNORECASE)


def _hydrate_path(value, app_root):
    if not isinstance(value, str):
        return value
    normalized = value.replace("\\", "/")
    replacements = (
        ("{{BUNDLED_DEMO_ROOT}}", f"{app_root}/demos"),
        ("{{BUNDLED_TRANSLATION_ROOT}}", f"{app_root}/my_translation"),
        ("{{DEMO_ROOT}}/demos", f"{app_root}/demos"),
        ("{{DEMO_ROOT}}", app_root),
    )
    bundled = bool(DEV_ROOT.match(normalized)) or any(
        normalized.startswith(old) for old, _new in replacements
    )
    if not bundled and not normalized.startswith(f"{app_root}/"):
        return value
    normalized = DEV_ROOT.sub(lambda _match: app_root, normalized)
    for old, new in replacements:
        normalized = normalized.replace(old, new)
    if bundled:
        normalized = normalized.replace("/source_mod/", "/demos/")
    folder_names = {
        "Multilanguage-Test_Project_Remis_Vic3": "en-Test_Project_Remis_Vic3",
        "zh-CN-Test_Project_Remis_Vic3": "en-Test_Project_Remis_Vic3",
        "Multilanguage-Test_Project_Remis_stellaris": "zh-CN-Test_Project_Remis_stellaris",
    }
    return "/".join(folder_names.get(part, part) for part in normalized.split("/"))


def _hydrate_fields(data, app_root):
    for section in (data, data.get("config")):
        if not isinstance(section, dict):
            continue
        for key in ("source_path", "target_path"):
            if key in section:
                section[key] = _hydrate_path(section[key], app_root)
        if isinstance(section.get("translation_dirs"), list):
            section["translation_dirs"] = [
                _hydrate_path(value, app_root) for value in section["translation_dirs"]
            ]


def _hydrate_sidecar(path, app_root):
    if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("Demo sidecar must not redirect writes")
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    if not isinstance(data, dict):
        raise ValueError("Demo sidecar must contain a JSON object")
    before = json.dumps(data, ensure_ascii=False)
    _hydrate_fields(data, app_root)
    if json.dumps(data, ensure_ascii=False) == before:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=4)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def hydrate_json_configs(app_data_dir):
    """Hydrate only declared path fields in demo/output sidecars."""
    app_root = Path(app_data_dir).resolve()
    for name in ("my_translation", "demos"):
        root = app_root / name
        for current, _, files in os.walk(root):
            if ".remis_project.json" not in files:
                continue
            path = Path(current) / ".remis_project.json"
            try:
                if not path.resolve().is_relative_to(app_root):
                    raise ValueError("Demo sidecar must remain inside AppData")
                _hydrate_sidecar(path, app_root.as_posix())
            except (OSError, ValueError, TypeError) as error:
                logger.error("Failed to hydrate JSON at %s: %s", path, error)
