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
