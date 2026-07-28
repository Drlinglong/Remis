import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_INTERNAL_VERSION = "3.0.7+1"
EXPECTED_PUBLIC_RELEASE = "3.0.7.1"


def _backend_version() -> str:
    settings = (ROOT / "scripts" / "app_settings.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*"([^"]+)"', settings, flags=re.MULTILINE)
    assert match is not None
    return match.group(1)


def _backend_update_date() -> str:
    settings = (ROOT / "scripts" / "app_settings.py").read_text(encoding="utf-8")
    match = re.search(
        r'^LAST_UPDATE_DATE\s*=\s*"([^"]+)"',
        settings,
        flags=re.MULTILINE,
    )
    assert match is not None
    return match.group(1)


def test_release_metadata_is_synchronized():
    package = json.loads(
        (ROOT / "scripts" / "react-ui" / "package.json").read_text(encoding="utf-8")
    )
    package_lock = json.loads(
        (ROOT / "scripts" / "react-ui" / "package-lock.json").read_text(
            encoding="utf-8"
        )
    )
    tauri_config = json.loads(
        (ROOT / "scripts" / "react-ui" / "src-tauri" / "tauri.conf.json").read_text(
            encoding="utf-8"
        )
    )
    cargo_toml = (
        ROOT / "scripts" / "react-ui" / "src-tauri" / "Cargo.toml"
    ).read_text(
        encoding="utf-8"
    )
    cargo_lock = (
        ROOT / "scripts" / "react-ui" / "src-tauri" / "Cargo.lock"
    ).read_text(encoding="utf-8")

    assert _backend_version() == EXPECTED_INTERNAL_VERSION
    assert package["version"] == EXPECTED_INTERNAL_VERSION
    assert package_lock["version"] == EXPECTED_INTERNAL_VERSION
    assert package_lock["packages"][""]["version"] == EXPECTED_INTERNAL_VERSION
    assert tauri_config["version"] == EXPECTED_INTERNAL_VERSION
    assert re.search(
        rf'^\[package\]\s+name = "remis-mod-factory"\s+version = "{re.escape(EXPECTED_INTERNAL_VERSION)}"',
        cargo_toml,
        flags=re.MULTILINE,
    )
    assert re.search(
        rf'name = "remis-mod-factory"\s+version = "{re.escape(EXPECTED_INTERNAL_VERSION)}"',
        cargo_lock,
    )
    assert _backend_update_date() == "2026-07-28"


def test_public_hotfix_version_maps_to_semver_build_metadata():
    base, metadata = EXPECTED_INTERNAL_VERSION.split("+", maxsplit=1)

    assert base == "3.0.7"
    assert metadata == "1"
    assert EXPECTED_PUBLIC_RELEASE == f"{base}.1"
