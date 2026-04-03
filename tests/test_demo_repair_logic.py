import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from scripts.core.db_initializer import fix_demo_paths, hydrate_json_configs


class TestDemoRepairLogic(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.demo_root = os.path.join(self.test_dir, "demos")
        self.translation_root = os.path.join(self.test_dir, "my_translation")
        os.makedirs(self.demo_root, exist_ok=True)
        os.makedirs(self.translation_root, exist_ok=True)

        self.db_path = os.path.join(self.test_dir, "test.sqlite")
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE projects (project_id TEXT, source_path TEXT, target_path TEXT, name TEXT)")
        self.cursor.execute("CREATE TABLE glossaries (glossary_id INTEGER PRIMARY KEY, game_id TEXT, name TEXT, is_main INTEGER)")
        self.cursor.execute("CREATE TABLE project_files (file_id TEXT, file_path TEXT)")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.test_dir)

    def test_fix_demo_paths_updates_database_and_folder_names(self):
        vic3_project_id = "a525f596-6c71-43fe-ade2-52c9205a2720"
        old_target = "C:/Users/Test/AppData/Roaming/RemisModFactory/my_translation/Multilanguage-Test_Project_Remis_Vic3"
        old_source = "J:/V3_Mod_Localization_Factory/source_mod/Test_Project_Remis_Vic3"
        old_file_path = "J:/V3_Mod_Localization_Factory/source_mod/Test_Project_Remis_Vic3/localisation/english/test_l_english.yml"

        self.cursor.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?)",
            (vic3_project_id, old_source, old_target, "Test Vic3"),
        )
        self.cursor.execute(
            "INSERT INTO project_files VALUES (?, ?)",
            ("file-1", old_file_path),
        )
        self.cursor.execute(
            "INSERT INTO glossaries (game_id, name, is_main) VALUES ('eu5', 'remis_demo_eu5', 0)"
        )
        self.conn.commit()

        os.makedirs(os.path.join(self.translation_root, "Multilanguage-Test_Project_Remis_Vic3"))

        fix_demo_paths(self.conn, self.demo_root, self.translation_root)

        self.cursor.execute("SELECT source_path, target_path FROM projects WHERE project_id = ?", (vic3_project_id,))
        source_path, target_path = self.cursor.fetchone()
        self.assertEqual(
            source_path,
            f"{self.demo_root.replace(os.sep, '/')}/Test_Project_Remis_Vic3",
        )
        self.assertTrue(target_path.endswith("zh-CN-Test_Project_Remis_Vic3"))

        self.cursor.execute("SELECT file_path FROM project_files WHERE file_id = 'file-1'")
        file_path = self.cursor.fetchone()[0]
        self.assertEqual(
            file_path,
            f"{self.demo_root.replace(os.sep, '/')}/Test_Project_Remis_Vic3/localisation/english/test_l_english.yml",
        )

        self.cursor.execute("SELECT is_main FROM glossaries WHERE name = 'remis_demo_eu5'")
        is_main = self.cursor.fetchone()[0]
        self.assertEqual(is_main, 1)

        self.assertFalse(os.path.exists(os.path.join(self.translation_root, "Multilanguage-Test_Project_Remis_Vic3")))
        self.assertTrue(os.path.exists(os.path.join(self.translation_root, "zh-CN-Test_Project_Remis_Vic3")))

    def test_fix_demo_paths_replaces_placeholders(self):
        self.cursor.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?)",
            (
                "proj-1",
                "{{BUNDLED_DEMO_ROOT}}/sample_mod",
                "{{BUNDLED_TRANSLATION_ROOT}}/sample_output",
                "Placeholder Test",
            ),
        )
        self.cursor.execute(
            "INSERT INTO project_files VALUES (?, ?)",
            ("file-2", "{{BUNDLED_DEMO_ROOT}}/sample_mod/localisation/english/test.yml"),
        )
        self.conn.commit()

        fix_demo_paths(self.conn, self.demo_root, self.translation_root)

        self.cursor.execute("SELECT source_path, target_path FROM projects WHERE project_id = 'proj-1'")
        source_path, target_path = self.cursor.fetchone()
        self.assertEqual(source_path, f"{self.demo_root.replace(os.sep, '/')}/sample_mod")
        self.assertEqual(target_path, f"{self.translation_root.replace(os.sep, '/')}/sample_output")

        self.cursor.execute("SELECT file_path FROM project_files WHERE file_id = 'file-2'")
        file_path = self.cursor.fetchone()[0]
        self.assertEqual(
            file_path,
            f"{self.demo_root.replace(os.sep, '/')}/sample_mod/localisation/english/test.yml",
        )

    def test_hydrate_json_configs_rewrites_legacy_paths(self):
        demos_dir = os.path.join(self.test_dir, "demos", "sample_mod")
        translations_dir = os.path.join(self.test_dir, "my_translation", "sample_output")
        os.makedirs(demos_dir, exist_ok=True)
        os.makedirs(translations_dir, exist_ok=True)

        payload = {
            "source_path": "J:/V3_Mod_Localization_Factory/source_mod/sample_mod",
            "translation_dirs": [
                "J:/V3_Mod_Localization_Factory/my_translation/Multilanguage-Test_Project_Remis_Vic3",
                "J:/V3_Mod_Localization_Factory/my_translation/Multilanguage-Test_Project_Remis_stellaris",
            ],
        }
        config_path = os.path.join(translations_dir, ".remis_project.json")
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        hydrate_json_configs(self.test_dir)

        with open(config_path, "r", encoding="utf-8") as handle:
            hydrated = json.load(handle)

        normalized_root = self.test_dir.replace("\\", "/")
        self.assertEqual(hydrated["source_path"], f"{normalized_root}/demos/sample_mod")
        self.assertIn(f"{normalized_root}/my_translation/zh-CN-Test_Project_Remis_Vic3", hydrated["translation_dirs"])
        self.assertIn(f"{normalized_root}/my_translation/zh-CN-Test_Project_Remis_stellaris", hydrated["translation_dirs"])


if __name__ == "__main__":
    unittest.main()
