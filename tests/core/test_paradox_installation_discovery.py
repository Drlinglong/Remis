from pathlib import Path

from scripts.core.services.paradox_installation_discovery import (
    discover_paradox_localizations,
    discover_steam_library_roots,
)


def _write_manifest(steamapps: Path, app_id: str, install_dir: str) -> None:
    steamapps.mkdir(parents=True, exist_ok=True)
    (steamapps / f"appmanifest_{app_id}.acf").write_text(
        f'"AppState"\n{{\n "appid" "{app_id}"\n "installdir" "{install_dir}"\n}}\n',
        encoding="utf-8",
    )


def test_discovers_localization_and_localisation_from_profile_rules(tmp_path):
    steam_root = tmp_path / "Steam"
    steamapps = steam_root / "steamapps"
    _write_manifest(steamapps, "529340", "Victoria 3")
    _write_manifest(steamapps, "281990", "Stellaris")
    (steamapps / "common" / "Victoria 3" / "game" / "localization").mkdir(parents=True)
    (steamapps / "common" / "Stellaris" / "game" / "localisation").mkdir(parents=True)
    profiles = {
        "1": {"id": "victoria3", "name": "Victoria 3", "source_localization_folder": "localization"},
        "2": {"id": "stellaris", "name": "Stellaris", "source_localization_folder": "localisation"},
    }

    results = discover_paradox_localizations(profiles, [steam_root])

    assert {item["game_id"] for item in results} == {"victoria3", "stellaris"}
    assert {Path(item["localization_path"]).name for item in results} == {
        "localization",
        "localisation",
    }


def test_libraryfolders_adds_non_default_steam_library(tmp_path):
    steam_root = tmp_path / "Steam"
    second_root = tmp_path / "多语言游戏库"
    (steam_root / "steamapps").mkdir(parents=True)
    (second_root / "steamapps").mkdir(parents=True)
    escaped = str(second_root).replace("\\", "\\\\")
    (steam_root / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n "1" {{ "path" "{escaped}" }}\n}}\n',
        encoding="utf-8",
    )

    libraries = discover_steam_library_roots([steam_root])

    assert steam_root.resolve() in libraries
    assert second_root.resolve() in libraries
