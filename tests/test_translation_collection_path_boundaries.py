"""Collection destination and cleanup boundaries under directory redirection."""
import asyncio
import os
from pathlib import Path
import subprocess

import pytest

from scripts.core.translation_collections import packaging


def _link_directory(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True, check=False,
        )
        if result.returncode:
            pytest.skip("Directory junction creation is unavailable on this host")
    else:
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("Directory symlink creation is unavailable on this host")


def _inspection():
    return {"can_export": True, "fingerprint": "preview", "mode": "portable_translations",
            "members": []}


@pytest.mark.asyncio
async def test_existing_junction_is_rejected_before_creating_any_outside_directory(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    linked = tmp_path / "export"
    _link_directory(linked, outside)

    async def inspect(_collection):
        return _inspection(), []

    monkeypatch.setattr(packaging, "_inspect", inspect)
    destination = linked / "collection" / "plan" / "mod"
    with pytest.raises(ValueError, match="linked directory or junction"):
        await packaging.build_collection({}, destination, "preview")
    assert list(outside.iterdir()) == [marker]
    assert marker.read_text(encoding="utf-8") == "keep"


async def _staged_export(tmp_path, monkeypatch):
    staged = asyncio.Event()
    calls = 0
    staging_paths = []

    async def inspect(_collection):
        nonlocal calls
        calls += 1
        if calls == 2:
            staged.set()
            await asyncio.Event().wait()
        return _inspection(), []

    def copy(staging, *_args):
        staging_paths.append(staging)
        (staging / "translated.txt").write_text("translated", encoding="utf-8")
        return 1

    monkeypatch.setattr(packaging, "_inspect", inspect)
    monkeypatch.setattr(packaging, "_copy_portable", copy)
    destination = tmp_path / "export" / "mod"
    task = asyncio.create_task(packaging.build_collection({}, destination, "preview"))
    await asyncio.wait_for(staged.wait(), timeout=5)
    return task, destination, staging_paths[0]


@pytest.mark.asyncio
async def test_cancel_after_parent_junction_swap_does_not_delete_external_staging(tmp_path, monkeypatch):
    task, destination, staging = await _staged_export(tmp_path, monkeypatch)
    parent = destination.parent
    displaced = tmp_path / "displaced"
    outside = tmp_path / "outside"
    external_staging = outside / staging.name
    external_staging.mkdir(parents=True)
    marker = external_staging / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    try:
        parent.rename(displaced)
        _link_directory(parent, outside)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert marker.read_text(encoding="utf-8") == "keep"
    assert (displaced / staging.name / "translated.txt").is_file()


@pytest.mark.asyncio
async def test_normal_staging_cancellation_still_cleans_captured_parent(tmp_path, monkeypatch):
    task, destination, staging = await _staged_export(tmp_path, monkeypatch)
    assert staging.is_dir()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not staging.exists()
    assert not destination.exists()
