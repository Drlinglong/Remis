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
