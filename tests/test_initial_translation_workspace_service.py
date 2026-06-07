import os

from scripts.core.services import initial_translation_workspace_service as workspace_service


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
