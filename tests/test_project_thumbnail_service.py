from pathlib import Path

import pytest

from scripts.core.services.project_thumbnail_service import find_project_thumbnail


def test_finds_supported_thumbnail_inside_project_root(tmp_path: Path):
    metadata = tmp_path / ".metadata"
    metadata.mkdir()
    thumbnail = metadata / "thumbnail.png"
    thumbnail.write_bytes(b"png")

    assert find_project_thumbnail(str(tmp_path)) == thumbnail.resolve()


def test_rejects_missing_project_root_and_thumbnail(tmp_path: Path):
    with pytest.raises(LookupError, match="source path is unavailable"):
        find_project_thumbnail(str(tmp_path / "missing"))

    with pytest.raises(LookupError, match="thumbnail not found"):
        find_project_thumbnail(str(tmp_path))
