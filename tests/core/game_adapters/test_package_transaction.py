"""Package writes restore the whole package when a multi-resource write fails."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.core.game_adapters import workflow_bridge
from scripts.core.game_adapters.registry import resource_adapter


def _fixture(tmp_path: Path):
    source_root = tmp_path / "source"
    about = source_root / "About/About.xml"
    defs = source_root / "Defs/Combined.xml"
    about.parent.mkdir(parents=True)
    defs.parent.mkdir(parents=True)
    about.write_text(
        "<ModMetaData><packageId>transaction.fixture</packageId></ModMetaData>",
        encoding="utf-8",
    )
    defs.write_text(
        "<Defs>"
        "<ThingDef><defName>Crystal</defName><label>crystal</label></ThingDef>"
        "<RecipeDef><defName>Polish</defName><jobString>polish crystal</jobString></RecipeDef>"
        "</Defs>",
        encoding="utf-8",
    )
    adapter = resource_adapter("rimworld")
    document = adapter.parse(defs, {
        "kind": "defs", "source_root": str(source_root),
        "project_root": str(source_root), "source_mod_id": "transaction.fixture",
        "relative_output_path": "Defs/Combined.xml", "game_version": "1.6",
    })
    assert {entry.metadata["def_type"] for entry in document.entries} == {
        "ThingDef", "RecipeDef"}
    return adapter, document


def _translations(document, prefix: str) -> list[str]:
    return [f"{prefix} {entry.value}" for entry in document.entries]


def _file_snapshot(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def _fail_third_atomic_write(monkeypatch):
    original = workflow_bridge.atomic_write
    calls = 0

    def fail_third(path: Path, content: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("synthetic disk failure on third package write")
        original(path, content)

    monkeypatch.setattr(workflow_bridge, "atomic_write", fail_third)


def _interrupt_after_third_atomic_write(monkeypatch):
    original = workflow_bridge.atomic_write
    calls = 0

    def interrupt_after_third(path: Path, content: str) -> None:
        nonlocal calls
        calls += 1
        original(path, content)
        if calls == 3:
            raise KeyboardInterrupt("synthetic interruption after third package write")

    monkeypatch.setattr(workflow_bridge, "atomic_write", interrupt_after_third)


def test_failed_new_package_write_leaves_no_partial_package(tmp_path, monkeypatch):
    adapter, document = _fixture(tmp_path)
    destination = tmp_path / "new-package"
    _fail_third_atomic_write(monkeypatch)

    with pytest.raises(OSError, match="third package write"):
        workflow_bridge.write_document(
            document, adapter.id, _translations(document, "first"),
            destination, {"code": "zh-CN"},
        )

    if destination.exists():
        assert _file_snapshot(destination) == {}
    assert not (destination / workflow_bridge.MANIFEST).exists()


def test_failed_update_restores_every_existing_package_file_and_manifest(
    tmp_path, monkeypatch,
):
    adapter, document = _fixture(tmp_path)
    destination = tmp_path / "existing-package"
    workflow_bridge.write_document(
        document, adapter.id, _translations(document, "first"),
        destination, {"code": "zh-CN"},
    )
    before = _file_snapshot(destination)
    manifest_path = destination / workflow_bridge.MANIFEST
    assert manifest_path.relative_to(destination).as_posix() in before
    _fail_third_atomic_write(monkeypatch)

    with pytest.raises(OSError, match="third package write"):
        workflow_bridge.write_document(
            document, adapter.id, _translations(document, "second"),
            destination, {"code": "zh-CN"},
        )

    assert _file_snapshot(destination) == before


@pytest.mark.parametrize(
    "existing_package", [False, True], ids=["new-package", "existing-package"],
)
def test_keyboard_interrupt_after_third_write_restores_package(
    tmp_path, monkeypatch, existing_package: bool,
):
    adapter, document = _fixture(tmp_path)
    destination = tmp_path / "existing-package" if existing_package else tmp_path / "new-package"
    if existing_package:
        workflow_bridge.write_document(
            document, adapter.id, _translations(document, "first"),
            destination, {"code": "zh-CN"},
        )
    before = _file_snapshot(destination) if destination.exists() else {}
    _interrupt_after_third_atomic_write(monkeypatch)

    with pytest.raises(KeyboardInterrupt, match="after third package write"):
        workflow_bridge.write_document(
            document, adapter.id,
            _translations(document, "second" if existing_package else "first"),
            destination, {"code": "zh-CN"},
        )

    assert _file_snapshot(destination) == before
