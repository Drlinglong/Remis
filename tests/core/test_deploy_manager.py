from scripts.core import deploy_manager as deploy_module
from scripts.core.deploy_manager import ModDeployer


def test_clean_fake_localization_rejects_non_mod_directory(tmp_path):
    deployer = ModDeployer()
    documents_dir = tmp_path / "Documents"
    documents_dir.mkdir()

    result = deployer.clean_fake_localization(str(documents_dir), source_lang="english")

    assert result["status"] == "error"
    assert "no 'localization' or 'localisation' directory" in result["message"]


def test_clean_fake_localization_removes_only_non_source_language_content(tmp_path):
    deployer = ModDeployer()
    mod_root = tmp_path / "12345678"
    loc_dir = mod_root / "localization"
    english_dir = loc_dir / "english"
    chinese_dir = loc_dir / "simp_chinese"
    english_dir.mkdir(parents=True)
    chinese_dir.mkdir()
    english_file = loc_dir / "demo_l_english.yml"
    chinese_file = loc_dir / "demo_l_simp_chinese.yml"
    english_file.write_text('l_english:\n key:0 "Value"\n', encoding="utf-8")
    chinese_file.write_text('l_simp_chinese:\n key:0 "Value"\n', encoding="utf-8")

    result = deployer.clean_fake_localization(str(mod_root), source_lang="english")

    assert result["status"] == "success"
    assert not chinese_dir.exists()
    assert not chinese_file.exists()
    assert english_dir.exists()
    assert english_file.exists()
    assert result["removed_folders"] == ["localization/simp_chinese"]
    assert result["removed_files"] == ["localization/demo_l_simp_chinese.yml"]


def test_clean_fake_localization_supports_localisation_spelling_and_language_alias(tmp_path):
    deployer = ModDeployer()
    mod_root = tmp_path / "alias-mod"
    loc_dir = mod_root / "localisation"
    source_dir = loc_dir / "simp_chinese"
    english_dir = loc_dir / "english"
    source_dir.mkdir(parents=True)
    english_dir.mkdir()
    source_file = loc_dir / "demo_l_simp_chinese.yml"
    english_file = loc_dir / "demo_l_english.yml"
    source_file.write_text('l_simp_chinese:\n key:0 "Value"\n', encoding="utf-8")
    english_file.write_text('l_english:\n key:0 "Value"\n', encoding="utf-8")

    result = deployer.clean_fake_localization(str(mod_root), source_lang="zh-CN")

    assert result["status"] == "success"
    assert source_dir.exists()
    assert source_file.exists()
    assert not english_dir.exists()
    assert not english_file.exists()
    assert result["removed_folders"] == ["localisation/english"]
    assert result["removed_files"] == ["localisation/demo_l_english.yml"]


def test_detect_steam_workshop_path_prefers_project_source_inside_workshop(tmp_path):
    deployer = ModDeployer()
    workshop_root = (
        tmp_path
        / "SteamLibrary"
        / "steamapps"
        / "workshop"
        / "content"
        / deployer.GAME_APPIDS["victoria3"]
    )
    mod_root = workshop_root / "123456789"
    mod_root.mkdir(parents=True)

    result = deployer.detect_steam_workshop_path("victoria3", str(mod_root))

    assert result == str(workshop_root)


def test_deploy_rejects_output_path_traversal(tmp_path, monkeypatch):
    destination = tmp_path / "translations"
    destination.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(deploy_module, "DEST_DIR", str(destination))
    deployer = ModDeployer()

    result = deployer.deploy_mod("../outside", "victoria3")

    assert result == {
        "status": "error",
        "message": "Deployment request was rejected by safety checks.",
    }
    assert marker.read_text(encoding="utf-8") == "keep"


def test_deploy_rejects_custom_target_outside_detected_mod_root(
    tmp_path,
    monkeypatch,
):
    destination = tmp_path / "translations"
    source = destination / "zh-CN-demo"
    source.mkdir(parents=True)
    (source / "localization.yml").write_text("demo", encoding="utf-8")
    mod_root = tmp_path / "Paradox" / "mod"
    mod_root.mkdir(parents=True)
    outside_target = tmp_path / "outside" / "zh-CN-demo"
    monkeypatch.setattr(deploy_module, "DEST_DIR", str(destination))
    deployer = ModDeployer()
    monkeypatch.setattr(
        deployer,
        "get_paradox_mod_dir",
        lambda _game_id: mod_root,
    )

    result = deployer.deploy_mod(
        "zh-CN-demo",
        "victoria3",
        target_deploy_path=str(outside_target),
    )

    assert result == {
        "status": "error",
        "message": "Deployment request was rejected by safety checks.",
    }
    assert not outside_target.exists()


def test_deploy_copies_known_output_to_detected_mod_root(tmp_path, monkeypatch):
    destination = tmp_path / "translations"
    source = destination / "zh-CN-demo"
    source.mkdir(parents=True)
    (source / "localization.yml").write_text("demo", encoding="utf-8")
    mod_root = tmp_path / "Paradox" / "mod"
    mod_root.mkdir(parents=True)
    monkeypatch.setattr(deploy_module, "DEST_DIR", str(destination))
    deployer = ModDeployer()
    monkeypatch.setattr(
        deployer,
        "get_paradox_mod_dir",
        lambda _game_id: mod_root,
    )

    result = deployer.deploy_mod("zh-CN-demo", "victoria3")

    deployed = mod_root / "zh-CN-demo" / "localization.yml"
    assert result["status"] == "success"
    assert deployed.read_text(encoding="utf-8") == "demo"


def test_deploy_does_not_return_internal_exception_details(tmp_path, monkeypatch):
    destination = tmp_path / "translations"
    source = destination / "zh-CN-demo"
    source.mkdir(parents=True)
    mod_root = tmp_path / "Paradox" / "mod"
    mod_root.mkdir(parents=True)
    monkeypatch.setattr(deploy_module, "DEST_DIR", str(destination))
    monkeypatch.setattr(
        deploy_module.shutil,
        "copytree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError(r"C:\Users\private\secret.txt")
        ),
    )
    deployer = ModDeployer()
    monkeypatch.setattr(
        deployer,
        "get_paradox_mod_dir",
        lambda _game_id: mod_root,
    )

    result = deployer.deploy_mod("zh-CN-demo", "victoria3")

    assert result == {
        "status": "error",
        "message": "Deployment failed. Check Remis logs for details.",
    }
