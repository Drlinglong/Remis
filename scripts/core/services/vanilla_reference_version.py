"""Version discovery for user-selected Paradox localization trees."""

import json
from pathlib import Path
import re


_ACF_FIELD_RE = re.compile(r'"(?P<key>[^"]+)"\s+"(?P<value>[^"]*)"')


def detect_reference_game_version(localization_root: Path) -> str:
    game_root = next(
        (
            candidate
            for candidate in (localization_root, *localization_root.parents)
            if candidate.parent.name.casefold() == "common"
            and candidate.parent.parent.name.casefold() == "steamapps"
        ),
        localization_root.parent.parent,
    )
    for directory in (localization_root, *localization_root.parents):
        launcher_path = directory / "launcher-settings.json"
        if launcher_path.is_file():
            try:
                payload = json.loads(launcher_path.read_text(encoding="utf-8-sig"))
                for key in ("rawVersion", "version", "gameVersion"):
                    value = str(payload.get(key, "")).strip()
                    if value:
                        return value
            except (OSError, ValueError, TypeError):
                pass
        version_path = directory / "version.txt"
        if version_path.is_file():
            try:
                value = version_path.read_text(encoding="utf-8-sig").strip()
                if value:
                    return value
            except OSError:
                pass

    common_root = game_root.parent
    steamapps_root = common_root.parent
    if common_root.name.casefold() != "common" or steamapps_root.name.casefold() != "steamapps":
        return "unknown"
    for manifest_path in steamapps_root.glob("appmanifest_*.acf"):
        try:
            fields = {
                match.group("key").casefold(): match.group("value")
                for match in _ACF_FIELD_RE.finditer(manifest_path.read_text(encoding="utf-8-sig"))
            }
        except OSError:
            continue
        if fields.get("installdir", "").casefold() != game_root.name.casefold():
            continue
        build_id = fields.get("buildid", "").strip()
        if build_id:
            return f"steam-build-{build_id}"
    return "unknown"
