from pathlib import Path

import pytest

from scripts.developer_tools.pytest_safety import validate_basetemp


def test_allows_default_system_temporary_directory():
    validate_basetemp(None)


def test_allows_explicit_temporary_directory_outside_repository(tmp_path: Path):
    repository_root = tmp_path / "checkout"
    external_temp = tmp_path / "system-temp" / "run-1"

    validate_basetemp(external_temp, repository_root)


def test_rejects_shared_temporary_directory_inside_repository(tmp_path: Path):
    repository_root = tmp_path / "checkout"
    shared_temp = repository_root / "build" / "pytest-temp"

    with pytest.raises(pytest.UsageError, match="must be outside"):
        validate_basetemp(shared_temp, repository_root)
