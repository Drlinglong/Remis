"""Explicit discovery of supported Paradox installations in Steam libraries."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import platform
import re
from typing import Iterable

from scripts.core.deploy_manager import ModDeployer


logger = logging.getLogger(__name__)
_VDF_PATH_RE = re.compile(r'"path"\s+"(?P<path>[^"]+)"', re.IGNORECASE)
_ACF_INSTALL_DIR_RE = re.compile(r'"installdir"\s+"(?P<name>[^"]+)"', re.IGNORECASE)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        logger.warning("Unable to read Steam metadata: %s", path)
        return ""


def _registry_steam_roots() -> list[Path]:
    if platform.system() != "Windows":
        return []
    try:
        import winreg
    except ImportError:
        return []

    roots: list[Path] = []
    locations = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
    )
    for hive, key_name in locations:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, "SteamPath")
        except OSError:
            continue
        if value:
            roots.append(Path(os.path.expandvars(str(value))))
    return roots


def discover_steam_library_roots(steam_roots: Iterable[str | Path] | None = None) -> list[Path]:
    """Return unique Steam library roots without scanning arbitrary drives."""

    candidates = [Path(item) for item in steam_roots] if steam_roots is not None else _registry_steam_roots()
    if steam_roots is None and platform.system() == "Windows":
        candidates.append(Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam")

    libraries: list[Path] = []
    for root in candidates:
        resolved = root.expanduser().resolve(strict=False)
        libraries.append(resolved)
        metadata = resolved / "steamapps" / "libraryfolders.vdf"
        for match in _VDF_PATH_RE.finditer(_read_text(metadata)):
            libraries.append(Path(match.group("path").replace("\\\\", "\\")).resolve(strict=False))

    unique: dict[str, Path] = {}
    for library in libraries:
        if (library / "steamapps").is_dir():
            unique.setdefault(os.path.normcase(str(library)), library)
    return list(unique.values())


def discover_paradox_localizations(
    game_profiles: dict,
    steam_roots: Iterable[str | Path] | None = None,
) -> list[dict]:
    """Find supported installed games from app manifests in known Steam libraries."""

    results: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for library in discover_steam_library_roots(steam_roots):
        steamapps = library / "steamapps"
        for profile in game_profiles.values():
            game_id = str(profile.get("id", ""))
            app_id = ModDeployer.GAME_APPIDS.get(game_id)
            if not app_id:
                continue
            manifest = steamapps / f"appmanifest_{app_id}.acf"
            match = _ACF_INSTALL_DIR_RE.search(_read_text(manifest))
            if not match:
                continue
            install_root = (steamapps / "common" / match.group("name")).resolve(strict=False)
            localization_roots = official_localization_roots(install_root, profile)
            identity = (game_id, os.path.normcase(str(install_root)))
            if identity in seen or not localization_roots:
                continue
            seen.add(identity)
            results.append({
                "game_id": game_id,
                "game_name": profile.get("name", game_id),
                "app_id": app_id,
                "localization_path": str(install_root),
                "localization_paths": [str(path) for path in localization_roots],
            })
    return results


def official_localization_roots(install_root: Path, profile: dict) -> list[Path]:
    """Resolve the official layout declared by a game profile."""

    patterns = profile.get("official_localization_globs") or [
        f"game/{profile.get('source_localization_folder', 'localization')}"
    ]
    roots: dict[str, Path] = {}
    for pattern in patterns:
        for candidate in install_root.glob(str(pattern)):
            if candidate.is_dir():
                resolved = candidate.resolve(strict=False)
                roots.setdefault(os.path.normcase(str(resolved)), resolved)
    return sorted(roots.values(), key=lambda item: os.path.normcase(str(item)))
