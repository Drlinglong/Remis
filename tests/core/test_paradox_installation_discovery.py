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


def test_discovers_official_layouts_without_assuming_a_game_subdirectory(tmp_path):
    steam_root = tmp_path / "Steam"
    steamapps = steam_root / "steamapps"
    _write_manifest(steamapps, "529340", "Victoria 3")
    _write_manifest(steamapps, "281990", "Stellaris")
    (steamapps / "common" / "Victoria 3" / "game" / "localization").mkdir(parents=True)
    (steamapps / "common" / "Stellaris" / "localisation").mkdir(parents=True)
    profiles = {
        "1": {
            "id": "victoria3",
            "name": "Victoria 3",
            "official_localization_globs": ["game/localization"],
        },
        "2": {
            "id": "stellaris",
            "name": "Stellaris",
            "official_localization_globs": ["localisation"],
        },
    }

    results = discover_paradox_localizations(profiles, [steam_root])

    assert {item["game_id"] for item in results} == {"victoria3", "stellaris"}
    assert {Path(item["localization_path"]).name for item in results} == {
        "Victoria 3",
        "Stellaris",
    }
    stellaris = next(item for item in results if item["game_id"] == "stellaris")
    assert stellaris["localization_paths"] == [
        str((steamapps / "common" / "Stellaris" / "localisation").resolve())
    ]


def test_discovers_all_eu5_official_localization_modules(tmp_path):
    steam_root = tmp_path / "Steam"
    steamapps = steam_root / "steamapps"
    _write_manifest(steamapps, "3450310", "Europa Universalis V")
    install_root = steamapps / "common" / "Europa Universalis V"
    expected = [
        install_root / "clausewitz" / "loading_screen" / "localization",
        install_root / "game" / "main_menu" / "localization",
        install_root / "game" / "dlc" / "D001" / "main_menu" / "localization",
        install_root / "jomini" / "in_game" / "localization",
    ]
    for root in expected:
        root.mkdir(parents=True)
    profiles = {
        "6": {
            "id": "eu5",
            "name": "Europa Universalis V",
            "official_localization_globs": [
                "clausewitz/**/localization",
                "game/**/localization",
                "jomini/**/localization",
            ],
        }
    }

    [candidate] = discover_paradox_localizations(profiles, [steam_root])

    assert candidate["localization_path"] == str(install_root.resolve())
    assert set(candidate["localization_paths"]) == {str(path.resolve()) for path in expected}


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
