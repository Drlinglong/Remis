import ast
import json
import tomllib
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
    cargo_manifest = tomllib.loads(
        (
            REPO_ROOT
            / "scripts"
            / "react-ui"
            / "src-tauri"
            / "Cargo.toml"
        ).read_text(encoding="utf-8")
    )

    assert {
        "scripts/app_settings.py": backend_version,
        "scripts/react-ui/package.json": package_json["version"],
        "scripts/react-ui/package-lock.json": package_lock["version"],
        "scripts/react-ui/package-lock.json packages['']": package_lock["packages"][""][
            "version"
        ],
        "scripts/react-ui/src-tauri/tauri.conf.json": tauri_config["version"],
        "scripts/react-ui/src-tauri/Cargo.toml": cargo_manifest["package"]["version"],
    } == {
        "scripts/app_settings.py": backend_version,
        "scripts/react-ui/package.json": backend_version,
        "scripts/react-ui/package-lock.json": backend_version,
        "scripts/react-ui/package-lock.json packages['']": backend_version,
        "scripts/react-ui/src-tauri/tauri.conf.json": backend_version,
        "scripts/react-ui/src-tauri/Cargo.toml": backend_version,
    }
