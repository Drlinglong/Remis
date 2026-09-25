import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.core.services import initial_translation_workspace_service as workspace_service
from scripts.core.services.translation_task_runtime import resolve_managed_output_path
from scripts.workflows.initial_translate import _unpack_prepared_run


def test_prepare_output_workspace_creates_structure_and_copies_assets(monkeypatch):
    calls = []

    monkeypatch.setattr(
        workspace_service.directory_handler,
        "create_output_structure",
        lambda mod_name, output_folder_name, game_profile: calls.append(
            ("structure", mod_name, output_folder_name, game_profile)
        ),
    )
    monkeypatch.setattr(
        workspace_service.asset_handler,
        "copy_assets",
        lambda mod_name, output_folder_name, game_profile: calls.append(
            ("assets", mod_name, output_folder_name, game_profile)
        ),
    )
    monkeypatch.setattr(workspace_service, "DEST_DIR", "J:/out")

    game_profile = {"id": "vic3"}
    result = workspace_service.prepare_output_workspace("Mod", "en-Mod", game_profile)

    assert result == os.path.join("J:/out", "en-Mod")
    assert calls == [
        ("structure", "Mod", "en-Mod", game_profile),
        ("assets", "Mod", "en-Mod", game_profile),
    ]


def test_prepare_output_workspace_rejects_output_traversal_before_copying(monkeypatch):
    calls = []
    monkeypatch.setattr(workspace_service, "DEST_DIR", "J:/out")
    monkeypatch.setattr(
        workspace_service.directory_handler,
        "create_output_structure",
        lambda *args: calls.append(args),
    )
    monkeypatch.setattr(
        workspace_service.asset_handler,
        "copy_assets",
        lambda *args: calls.append(args),
    )

    with pytest.raises(ValueError, match="single safe path component"):
        workspace_service.prepare_output_workspace(
            "Mod", "../../outside", {"id": "victoria3"}
        )
    assert calls == []


def test_managed_output_path_rejects_symlinked_output_root(tmp_path, monkeypatch):
    dest_root = tmp_path / "outputs"
    dest_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_output = dest_root / "safe-output"
    original_resolve = Path.resolve

    def resolve_with_external_link(path, *args, **kwargs):
        if path == linked_output:
            return outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_with_external_link)

    with pytest.raises(ValueError, match="outside"):
        resolve_managed_output_path("safe-output", dest_root=str(dest_root))


def test_clean_source_directory_keeps_localization_and_metadata(tmp_path):
    (tmp_path / "localization").mkdir()
    (tmp_path / "customizable_localization").mkdir()
    (tmp_path / "descriptor.mod").write_text("name=Test", encoding="utf-8")
    (tmp_path / "thumbnail.png").write_bytes(b"png")

    removable_dir = tmp_path / "gfx"
    removable_dir.mkdir()
    (removable_dir / "asset.txt").write_text("asset", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("remove me", encoding="utf-8")

    workspace_service.clean_source_directory("ignored", override_path=str(tmp_path))

    assert (tmp_path / "localization").exists()
    assert (tmp_path / "customizable_localization").exists()
    assert (tmp_path / "descriptor.mod").exists()
    assert (tmp_path / "thumbnail.png").exists()
    assert not removable_dir.exists()
    assert not (tmp_path / "notes.txt").exists()


def test_prepared_run_uses_snapshot_after_clean_source():
    prepared = SimpleNamespace(
        output_dir_path="out",
        source_result="source-result",
        all_files_content=[],
        context_selection=None,
        total_batches=0,
        version_id=1,
        source_root="source",
        source_snapshot_hash="snapshot-after-clean",
        effective_chunk_size=1,
    )

    unpacked = _unpack_prepared_run(
        prepared,
        {"source_snapshot_hash": "snapshot-before-clean"},
    )

    assert unpacked[-2] == "snapshot-after-clean"
