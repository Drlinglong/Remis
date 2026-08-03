from pathlib import Path

from scripts.app_settings import get_static_config_dir


def test_frozen_build_reads_versioned_config_from_bundled_resources(tmp_path):
    resource_dir = tmp_path / "bundle"
    project_root = tmp_path / "checkout"

    config_dir = get_static_config_dir(
        str(resource_dir),
        str(project_root),
        frozen=True,
    )

    assert Path(config_dir) == resource_dir / "data" / "config"


def test_development_build_reads_versioned_config_from_checkout(tmp_path):
    resource_dir = tmp_path / "bundle"
    project_root = tmp_path / "checkout"

    config_dir = get_static_config_dir(
        str(resource_dir),
        str(project_root),
        frozen=False,
    )

    assert Path(config_dir) == project_root / "data" / "config"
