from scripts.core import db_initializer


def test_sync_development_demo_sources_copies_known_demos_only(tmp_path):
    source_mod = tmp_path / "source_mod"
    demos = tmp_path / "demos"

    vic3_file = source_mod / "Test_Project_Remis_Vic3" / "localization" / "simp_chinese" / "remis_demo_l_simp_chinese.yml"
    vic3_file.parent.mkdir(parents=True)
    vic3_file.write_text('l_simp_chinese:\n key:0 "#r 泰尔紫#!。"', encoding="utf-8")

    user_mod_file = source_mod / "User_Mod" / "localization" / "simp_chinese" / "user.yml"
    user_mod_file.parent.mkdir(parents=True)
    user_mod_file.write_text("should not be copied", encoding="utf-8")

    assert db_initializer.sync_development_demo_sources(str(source_mod), str(demos)) is True

    copied_vic3_file = demos / "Test_Project_Remis_Vic3" / "localization" / "simp_chinese" / "remis_demo_l_simp_chinese.yml"
    assert copied_vic3_file.read_text(encoding="utf-8") == 'l_simp_chinese:\n key:0 "#r 泰尔紫#!。"'
    assert not (demos / "User_Mod").exists()


def test_sync_development_demo_sources_returns_false_without_source_mod(tmp_path):
    assert db_initializer.sync_development_demo_sources(str(tmp_path / "missing"), str(tmp_path / "demos")) is False
