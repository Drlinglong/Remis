import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import shutil
import tempfile
from scripts.core.project_manager import ProjectManager
import scripts.app_settings as app_settings

class TestProjectManager(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        # 1. Mock Dependencies
        self.mock_file_service = MagicMock()
        # Set async methods on file service mock
        self.mock_file_service.scan_and_sync_files = AsyncMock()

        self.mock_repo = MagicMock()
        # Set async methods on repo mock
        self.mock_repo.create_project = AsyncMock()
        self.mock_repo.get_project = AsyncMock()
        self.mock_repo.list_projects = AsyncMock()
        self.mock_repo.get_project_files = AsyncMock()
        self.mock_repo.update_project_status = AsyncMock()
        self.mock_repo.update_project_notes = AsyncMock()
        self.mock_repo.add_history_entry = AsyncMock()
        self.mock_repo.touch_project = AsyncMock()
        self.mock_repo.update_project_metadata = AsyncMock()
        
        self.mock_kanban = MagicMock()
        
        # 2. Instantiate ProjectManager with Injected Mocks
        self.pm = ProjectManager(
            file_service=self.mock_file_service,
            project_repository=self.mock_repo,
            kanban_service=self.mock_kanban,
            db_path=":memory:" 
        )

    @patch("scripts.core.project_manager.ProjectJsonManager")
    @patch("scripts.core.project_manager.os.path.exists")
    @patch("scripts.core.project_manager.shutil.copytree")
    async def test_create_project_success(self, mock_copy, mock_exists, mock_json_mgr):
        """
        Test creating a project successfully invokes repository and file service.
        """
        # Setup
        mock_exists.return_value = False
        
        # Mock Repository returning a valid Project object
        mock_pydantic_proj = MagicMock()
        mock_pydantic_proj.model_dump.return_value = {
            "id": "123", 
            "name": "TestProj", 
            "source_path": "J:/Mods/MyMod"
        }
        # Make access via ['key'] work for manager internal logic that accesses dict
        mock_pydantic_proj.__getitem__ = lambda s, k: mock_pydantic_proj.model_dump.return_value[k]
        
        self.mock_repo.create_project.return_value = mock_pydantic_proj
        
        # Also need get_project to return something for refresh_project_files
        self.mock_repo.get_project.return_value = mock_pydantic_proj
        
        # Actions
        result = await self.pm.create_project(
            name="Test Project", 
            folder_path="J:/Mods/MyMod", 
            game_id="vic3", 
            source_language="english"
        )

        # Assertions
        # 1. Repository called
        self.mock_repo.create_project.assert_called_once()
        
        # 2. JSON Sidecar initialized
        mock_json_mgr.assert_called()
        
        # 3. File Refresh Triggered
        self.mock_file_service.scan_and_sync_files.assert_called_once()
        
        self.assertEqual(result["id"], "123")

    @patch("scripts.core.project_manager.ProjectJsonManager")
    async def test_create_project_copies_detected_localization_scope(self, mock_json_mgr):
        """
        Large mod imports should copy known localization/metadata paths instead of the whole mod tree.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_root = os.path.join(temp_dir, "HugeMod")
            source_root = os.path.join(temp_dir, "source_mod")
            os.makedirs(os.path.join(mod_root, "localisation"), exist_ok=True)
            os.makedirs(os.path.join(mod_root, "gfx", "large_assets"), exist_ok=True)
            os.makedirs(source_root, exist_ok=True)
            with open(os.path.join(mod_root, "localisation", "demo_l_english.yml"), "w", encoding="utf-8") as handle:
                handle.write("l_english:\n demo_key:0 \"Demo\"\n")
            with open(os.path.join(mod_root, "descriptor.mod"), "w", encoding="utf-8") as handle:
                handle.write("name=\"HugeMod\"\n")
            with open(os.path.join(mod_root, "gfx", "large_assets", "skip.bin"), "w", encoding="utf-8") as handle:
                handle.write("not localization")

            mock_pydantic_proj = MagicMock()
            mock_pydantic_proj.model_dump.return_value = {
                "project_id": "scoped-copy",
                "name": "HugeMod",
                "source_path": os.path.join(source_root, "HugeMod"),
                "game_id": "hoi4",
            }
            self.mock_repo.create_project.return_value = mock_pydantic_proj
            self.mock_repo.get_project.return_value = mock_pydantic_proj

            with patch("scripts.core.project_manager.SOURCE_DIR", source_root):
                await self.pm.create_project(
                    name="HugeMod",
                    folder_path=mod_root,
                    game_id="hoi4",
                    source_language="en",
                    import_mode="copy",
                )

            copied_root = os.path.join(source_root, "HugeMod")
            self.assertTrue(os.path.exists(os.path.join(copied_root, "localisation", "demo_l_english.yml")))
            self.assertTrue(os.path.exists(os.path.join(copied_root, "descriptor.mod")))
            self.assertFalse(os.path.exists(os.path.join(copied_root, "gfx", "large_assets", "skip.bin")))
            mock_json_mgr.return_value.update_config.assert_called_once()
            config_payload = mock_json_mgr.return_value.update_config.call_args.args[0]
            self.assertEqual(config_payload["project_import"]["copy_scope"], "selected")

    @patch("scripts.core.project_manager.ProjectJsonManager")
    async def test_create_project_reference_mode_normalizes_localization_subfolder_to_mod_root(self, mock_json_mgr):
        """
        Selecting TNO/localisation should still register TNO as the project root so metadata stays visible.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_root = os.path.join(temp_dir, "TNO")
            source_root = os.path.join(temp_dir, "source_mod")
            localisation_dir = os.path.join(mod_root, "localisation")
            os.makedirs(localisation_dir, exist_ok=True)
            os.makedirs(source_root, exist_ok=True)
            with open(os.path.join(mod_root, "descriptor.mod"), "w", encoding="utf-8") as handle:
                handle.write("name=\"TNO\"\n")

            mock_pydantic_proj = MagicMock()
            mock_pydantic_proj.model_dump.return_value = {
                "project_id": "reference-root",
                "name": "TNO",
                "source_path": mod_root,
                "game_id": "hoi4",
            }
            self.mock_repo.create_project.return_value = mock_pydantic_proj
            self.mock_repo.get_project.return_value = mock_pydantic_proj

            with patch("scripts.core.project_manager.SOURCE_DIR", source_root), patch(
                "scripts.core.project_manager.shutil.copytree"
            ) as mock_copytree:
                await self.pm.create_project(
                    name="TNO",
                    folder_path=localisation_dir,
                    game_id="hoi4",
                    source_language="en",
                    import_mode="reference",
                )

            created_project = self.mock_repo.create_project.call_args.args[0]
            self.assertEqual(created_project.source_path, os.path.abspath(mod_root))
            mock_json_mgr.assert_called_with(os.path.abspath(mod_root))
            mock_copytree.assert_not_called()
            config_payload = mock_json_mgr.return_value.update_config.call_args.args[0]
            self.assertEqual(config_payload["project_import"]["selected_path"], os.path.abspath(localisation_dir))
            self.assertEqual(config_payload["project_import"]["original_path"], os.path.abspath(mod_root))
            self.assertEqual(config_payload["project_import"]["import_mode"], "reference")

    async def test_refresh_project_files_delegation(self):
        """
        Test that refresh_project_files correctly delegates to FileService.
        """
        # Setup
        project_id = "test-123"
        mock_proj_data = {"id": project_id, "name": "Test", "source_path": "/path/to/source"}
        
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = mock_proj_data
        # Make mock object subscriptable for project['source_path'] access in manager
        mock_obj.__getitem__ = lambda s, k: mock_proj_data[k]
        
        self.mock_repo.get_project.return_value = mock_obj

        # Patch ProjectJsonManager to avoid disk I/O for translation_dirs
        with patch("scripts.core.project_manager.ProjectJsonManager") as MockJson:
            MockJson.return_value.get_config.return_value = {"translation_dirs": ["/trans/path"]}
            
            # Action
            await self.pm.refresh_project_files(project_id)
            
            # Assertion
            self.mock_file_service.scan_and_sync_files.assert_called_once_with(
                project_id, 
                "/path/to/source", 
                ["/trans/path"], 
                "Test"
            )

    async def test_update_project_metadata(self):
        """
        Verify metadata update flows to repository calls correctly.
        """
        project_id = "test-meta"
        mock_proj_data = {"id": project_id, "source_path": "/dummy"}
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = mock_proj_data
        mock_obj.__getitem__ = lambda s, k: mock_proj_data[k]
        
        self.mock_repo.get_project.return_value = mock_obj
        
        with patch("scripts.core.project_manager.ProjectJsonManager"):
            await self.pm.update_project_metadata(project_id, "stellaris", "english")
        
        # Assert aliases handled ("stellaris" -> "stellaris")
        self.mock_repo.update_project_metadata.assert_called_once_with(
            project_id, "stellaris", "english"
        )

    async def test_run_incremental_update_workflow_falls_back_to_defaults(self):
        """
        Unknown source language and game ID should fall back to English and victoria3.
        """
        project_id = "workflow-proj"
        mock_proj_data = {
            "project_id": project_id,
            "source_language": "unknown-language",
            "game_id": "missing-game",
        }
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = mock_proj_data
        self.mock_repo.get_project.return_value = mock_obj

        config = MagicMock()
        config.project_id = project_id
        config.target_lang_codes = [MagicMock(value="zh-CN"), MagicMock(value="missing-lang")]
        config.api_provider = "test-provider"
        config.model = "test-model"
        config.batch_size_limit = None
        config.concurrency_limit = None
        config.rpm_limit = None
        config.dry_run = False
        config.custom_source_path = None
        config.use_resume = True
        config.embedded_workshop = None

        with patch.dict(
            app_settings.LANGUAGE_BY_CODE,
            {"en": {"code": "en"}, "zh-CN": {"code": "zh-CN"}},
            clear=True,
        ), patch.dict(
            app_settings.GAME_PROFILES_BY_ID,
            {"victoria3": {"id": "victoria3"}},
            clear=True,
        ), patch.dict(
            app_settings.GAME_PROFILES,
            {},
            clear=True,
        ), patch(
            "scripts.workflows.update_translate.run_incremental_update",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = {"status": "completed"}

            result = await self.pm.run_incremental_update_workflow(config)

        self.assertEqual(result, {"status": "completed"})
        mock_run.assert_awaited_once_with(
            project_id=project_id,
            target_lang_infos=[{"code": "zh-CN"}],
            source_lang_info={"code": "en"},
            game_profile={"id": "victoria3"},
            selected_provider="test-provider",
            model_name="test-model",
            batch_size_limit=None,
            concurrency_limit=None,
            rpm_limit=None,
            dry_run=False,
            custom_source_path=None,
            use_resume=True,
            embedded_workshop=None,
            progress_callback=None,
        )

    async def test_check_project_archive_uses_detected_language_fallback(self):
        """
        Archive inspection should default target_language to zh-CN when detection fails.
        """
        project_id = "archive-proj"
        mock_proj_data = {"project_id": project_id, "name": "Archive Demo"}
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = mock_proj_data
        self.mock_repo.get_project.return_value = mock_obj

        archive_manager = MagicMock()
        archive_manager.get_latest_version.return_value = {
            "id": "ver-1",
            "created_at": "2026-04-04T00:00:00",
        }
        archive_manager.get_archived_languages.return_value = ["zh-CN", "ru"]
        archive_manager.detect_target_language.return_value = None
        archive_manager.get_source_entry_count.return_value = None
        archive_manager.get_source_file_count.return_value = None
        archive_manager.get_total_translated_entry_count.return_value = None
        self.pm.archive_service.archive_manager = archive_manager

        result = await self.pm.check_project_archive(project_id)

        self.assertTrue(result["exists"])
        self.assertEqual(result["version_id"], "ver-1")
        self.assertEqual(result["created_at"], "2026-04-04T00:00:00")
        self.assertEqual(result["target_language"], "zh-CN")
        self.assertEqual(result["target_languages"], ["zh-CN", "ru"])
        self.assertEqual(result["archived_languages"], ["zh-CN", "ru"])
        self.assertEqual(result["project_name"], "Archive Demo")
        self.assertEqual(
            result["baseline_versions"],
            [
                {
                    "language": "zh-CN",
                    "version_id": "ver-1",
                    "created_at": "2026-04-04T00:00:00",
                    "last_translation_at": None,
                    "translated_count": None,
                },
                {
                    "language": "ru",
                    "version_id": "ver-1",
                    "created_at": "2026-04-04T00:00:00",
                    "last_translation_at": None,
                    "translated_count": None,
                },
            ],
        )
        self.assertIsNone(result["source_entry_count"])
        self.assertIsNone(result["source_file_count"])
        self.assertIsNone(result["total_translation_entries"])
        self.assertEqual(result["target_language_count"], 2)
        self.assertIsNone(result["last_upload_at"])

if __name__ == '__main__':
    unittest.main()
