import ast
import datetime as dt
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_python_constant(module_path: Path, name: str) -> str:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not defined in {module_path}")


def _read_cargo_package_version(manifest_path: Path) -> str:
    manifest = manifest_path.read_text(encoding="utf-8")
    match = re.search(
        r'^\[package\]\s+name = "remis-mod-factory"\s+version = "([^"]+)"',
        manifest,
        flags=re.MULTILINE,
    )
    assert match is not None
    return match.group(1)


def _read_cargo_lock_version(lock_path: Path) -> str:
    lockfile = lock_path.read_text(encoding="utf-8")
    match = re.search(
        r'name = "remis-mod-factory"\s+version = "([^"]+)"',
        lockfile,
    )
    assert match is not None
    return match.group(1)


def test_release_version_metadata_stays_in_sync():
    backend_version = _read_python_constant(
        REPO_ROOT / "scripts" / "app_settings.py",
        "VERSION",
    )
    package_json = json.loads(
        (REPO_ROOT / "scripts" / "react-ui" / "package.json").read_text(
            encoding="utf-8",
        )
    )
    package_lock = json.loads(
        (REPO_ROOT / "scripts" / "react-ui" / "package-lock.json").read_text(
            encoding="utf-8",
        )
    )
    tauri_config = json.loads(
        (
            REPO_ROOT
            / "scripts"
            / "react-ui"
            / "src-tauri"
            / "tauri.conf.json"
        ).read_text(encoding="utf-8")
    )
    cargo_manifest_version = _read_cargo_package_version(
        REPO_ROOT / "scripts" / "react-ui" / "src-tauri" / "Cargo.toml"
    )
    cargo_lock_version = _read_cargo_lock_version(
        REPO_ROOT / "scripts" / "react-ui" / "src-tauri" / "Cargo.lock"
    )

    assert {
        "scripts/app_settings.py": backend_version,
        "scripts/react-ui/package.json": package_json["version"],
        "scripts/react-ui/package-lock.json": package_lock["version"],
        "scripts/react-ui/package-lock.json packages['']": package_lock["packages"][""][
            "version"
        ],
        "scripts/react-ui/src-tauri/tauri.conf.json": tauri_config["version"],
        "scripts/react-ui/src-tauri/Cargo.toml": cargo_manifest_version,
        "scripts/react-ui/src-tauri/Cargo.lock": cargo_lock_version,
    } == {
        "scripts/app_settings.py": backend_version,
        "scripts/react-ui/package.json": backend_version,
        "scripts/react-ui/package-lock.json": backend_version,
        "scripts/react-ui/package-lock.json packages['']": backend_version,
        "scripts/react-ui/src-tauri/tauri.conf.json": backend_version,
        "scripts/react-ui/src-tauri/Cargo.toml": backend_version,
        "scripts/react-ui/src-tauri/Cargo.lock": backend_version,
    }


def test_release_date_is_current_and_visible_in_version_info():
    package_json = json.loads(
        (REPO_ROOT / "scripts" / "react-ui" / "package.json").read_text(
            encoding="utf-8",
        )
    )
    backend_release_date = _read_python_constant(
        REPO_ROOT / "scripts" / "app_settings.py",
        "LAST_UPDATE_DATE",
    )
    release_date = dt.date.fromisoformat(package_json["releaseDate"])
    release_note = (
        REPO_ROOT
        / "archive"
        / "release_notes"
        / f"RELEASE_NOTES_v{package_json['version']}.md"
    ).read_text(encoding="utf-8")
    version_info = (
        REPO_ROOT
        / "scripts"
        / "react-ui"
        / "src"
        / "components"
        / "VersionInfoTab.jsx"
    ).read_text(encoding="utf-8")

    assert f"Released on {release_date.isoformat()}." in release_note
    assert backend_release_date == release_date.isoformat()
    assert "const lastUpdated = __APP_RELEASE_DATE__" in version_info
