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
        self.mock_repo.update_project_lifecycle_status = AsyncMock()
        self.mock_repo.update_project_notes = AsyncMock()
        self.mock_repo.add_history_entry = AsyncMock()
        self.mock_repo.touch_project = AsyncMock()
        self.mock_repo.update_project_metadata = AsyncMock()
        self.mock_repo.update_project_source_path = AsyncMock()
        
        self.mock_kanban = MagicMock()
        
        # 2. Instantiate ProjectManager with Injected Mocks
        self.pm = ProjectManager(
            file_service=self.mock_file_service,
            project_repository=self.mock_repo,
            kanban_service=self.mock_kanban,
            db_path=":memory:" 
        )

    async def test_update_project_status_uses_atomic_lifecycle_transition(self):
        lifecycle = {
            "status": "archived",
            "paused_watch_count": 2,
            "restored_watch_count": 0,
        }
        self.mock_repo.update_project_lifecycle_status.return_value = lifecycle

        result = await self.pm.update_project_status("project-1", "archived")

        self.assertEqual(result, lifecycle)
        self.mock_repo.update_project_lifecycle_status.assert_awaited_once_with(
            "project-1",
            "archived",
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

    @patch("scripts.core.project_manager.ProjectJsonManager")
    async def test_create_project_copy_mode_renames_target_when_source_dir_name_conflicts(self, mock_json_mgr):
        """
        Copy-mode imports should append a numeric suffix when the destination folder already exists.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_root = os.path.join(temp_dir, "HugeMod")
            source_root = os.path.join(temp_dir, "source_mod")
            os.makedirs(os.path.join(mod_root, "localisation"), exist_ok=True)
            os.makedirs(os.path.join(source_root, "HugeMod"), exist_ok=True)
            with open(os.path.join(mod_root, "descriptor.mod"), "w", encoding="utf-8") as handle:
                handle.write("name=\"HugeMod\"\n")

            mock_pydantic_proj = MagicMock()
            mock_pydantic_proj.model_dump.return_value = {
                "project_id": "renamed-copy",
                "name": "HugeMod",
                "source_path": os.path.join(source_root, "HugeMod_1"),
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

            created_project = self.mock_repo.create_project.call_args.args[0]
            expected_target = os.path.join(source_root, "HugeMod_1")
            self.assertEqual(created_project.source_path, expected_target)
            self.assertTrue(os.path.exists(os.path.join(expected_target, "descriptor.mod")))
            config_payload = mock_json_mgr.return_value.update_config.call_args.args[0]
            self.assertEqual(config_payload["project_import"]["copy_scope"], "selected")
            self.assertEqual(config_payload["project_import"]["original_path"], os.path.abspath(mod_root))

    async def test_get_project_normalizes_legacy_localisation_subfolder_and_persists_it(self):
        """
        Legacy projects stored at the localisation folder should be normalized back to the mod root.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            mod_root = os.path.join(temp_dir, "TNO")
            localisation_dir = os.path.join(mod_root, "localisation")
            os.makedirs(localisation_dir, exist_ok=True)
            with open(os.path.join(mod_root, "descriptor.mod"), "w", encoding="utf-8") as handle:
                handle.write("name=\"TNO\"\n")

            mock_obj = MagicMock()
            mock_obj.model_dump.return_value = {
                "project_id": "legacy-proj",
                "name": "TNO",
                "game_id": "hoi4",
                "source_path": localisation_dir,
            }
            self.mock_repo.get_project.return_value = mock_obj

            result = await self.pm.get_project("legacy-proj")

        self.assertEqual(result["source_path"], os.path.abspath(mod_root))
        self.mock_repo.update_project_source_path.assert_awaited_once_with(
            "legacy-proj",
            os.path.abspath(mod_root),
        )

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

    async def test_add_translation_path_refreshes_existing_directory_index(self):
        """
        A reused incremental output directory may contain a different file set
        after a later run and must be rescanned even when already registered.
        """
        project_id = "incremental-project"
        translation_path = os.path.abspath("/translation/reused-output")
        project_data = {
            "project_id": project_id,
            "name": "Incremental Project",
            "source_path": "/path/to/source",
        }
        mock_project = MagicMock()
        mock_project.model_dump.return_value = project_data
        mock_project.__getitem__ = lambda s, k: project_data[k]
        self.mock_repo.get_project.return_value = mock_project
        self.pm.refresh_project_files = AsyncMock()
        self.pm.log_history_event = AsyncMock()

        with patch("scripts.core.project_manager.ProjectJsonManager") as mock_json_manager:
            manager = mock_json_manager.return_value
            manager.get_config.return_value = {
                "translation_dirs": [translation_path],
            }

            await self.pm.add_translation_path(project_id, translation_path)

        manager.update_config.assert_not_called()
        self.pm.log_history_event.assert_not_awaited()
        self.pm.refresh_project_files.assert_awaited_once_with(project_id)

    async def test_get_project_kanban_reconciles_sidecar_with_db_files(self):
        project_id = "kanban-proj"
        project_data = {"project_id": project_id, "name": "Kanban", "source_path": "/path/to/source"}
        mock_project = MagicMock()
        mock_project.model_dump.return_value = project_data
        mock_project.__getitem__ = lambda s, k: project_data[k]
        mock_file = MagicMock()
        mock_file.model_dump.return_value = {
            "file_id": "source-id",
            "project_id": project_id,
            "file_path": "/path/to/source/localisation/demo_l_english.yml",
            "status": "todo",
            "file_type": "source",
        }
        self.mock_repo.get_project.return_value = mock_project
        self.mock_repo.get_project_files.return_value = [mock_file]
        self.mock_kanban.sync_board_to_files.return_value = {"tasks": {"source-id": {}}}

        result = await self.pm.get_project_kanban(project_id)

        self.assertEqual(result, {"tasks": {"source-id": {}}})
        self.mock_kanban.sync_board_to_files.assert_called_once_with(
            "/path/to/source",
            [mock_file.model_dump.return_value],
        )

    async def test_repair_project_metadata_rebuilds_sidecars_and_refreshes_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = os.path.join(temp_dir, "project")
            translation_root = os.path.join(temp_dir, "translation")
            os.makedirs(source_root)
            os.makedirs(translation_root)
            sidecar_path = os.path.join(source_root, ".remis_project.json")
            with open(sidecar_path, "w", encoding="utf-8") as handle:
                handle.write("{broken json")
            with open(os.path.join(source_root, ".remis_errors.json"), "w", encoding="utf-8") as handle:
                handle.write("[{\"file_name\":\"../translation/demo_l_english.yml\",\"source_context_status\":\"missing\"}]")

            mock_obj = MagicMock()
            mock_obj.model_dump.return_value = {
                "project_id": "repair-proj",
                "name": "Repair Project",
                "game_id": "hoi4",
                "source_language": "zh-CN",
                "source_path": source_root,
            }
            self.mock_repo.get_project.return_value = mock_obj
            self.mock_repo.get_project_files.return_value = [
                MagicMock(model_dump=MagicMock(return_value={"file_path": "one.yml"}))
            ]

            result = await self.pm.repair_project_metadata("repair-proj")

        self.assertEqual(result["status"], "success")
        self.assertIn("cleared_stale_project_error_cache", result["actions"])
        self.assertEqual(result["error_cache_status"], "cleared_stale")
        self.assertEqual(result["file_count"], 1)
        self.mock_file_service.scan_and_sync_files.assert_called()

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

    async def test_update_source_path_migrates_sidecar_and_updates_repository(self):
        """
        Source path migration should live in ProjectManager, not the router.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            old_source = os.path.join(temp_dir, "old_mod")
            new_source = os.path.join(temp_dir, "new_mod")
            os.makedirs(old_source)
            os.makedirs(new_source)
            sidecar_path = os.path.join(old_source, ".remis_project.json")
            with open(sidecar_path, "w", encoding="utf-8") as handle:
                handle.write('{"config": {"translation_dirs": []}}')

            mock_obj = MagicMock()
            mock_obj.model_dump.return_value = {
                "project_id": "source-proj",
                "name": "Source Project",
                "game_id": "hoi4",
                "source_path": old_source,
            }
            self.mock_repo.get_project.return_value = mock_obj

            await self.pm.update_source_path("source-proj", new_source)

            self.assertTrue(os.path.exists(os.path.join(new_source, ".remis_project.json")))
            self.mock_repo.touch_project.assert_awaited_once_with("source-proj")
            self.mock_repo.update_project_source_path.assert_awaited_once_with(
                "source-proj",
                os.path.abspath(new_source),
            )

    async def test_update_source_path_rejects_missing_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old_source = os.path.join(temp_dir, "old_mod")
            missing_source = os.path.join(temp_dir, "missing_mod")
            os.makedirs(old_source)

            mock_obj = MagicMock()
            mock_obj.model_dump.return_value = {
                "project_id": "missing-source-proj",
                "name": "Missing Source Project",
                "game_id": "hoi4",
                "source_path": old_source,
            }
            self.mock_repo.get_project.return_value = mock_obj

            with self.assertRaisesRegex(ValueError, "Source directory not found"):
                await self.pm.update_source_path("missing-source-proj", missing_source)

            self.mock_repo.update_project_source_path.assert_not_called()

    async def test_promote_incremental_source_refreshes_managed_copy_in_place(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            managed_root = os.path.join(temp_dir, "managed")
            current_source = os.path.join(managed_root, "demo")
            candidate_source = os.path.join(temp_dir, "new-version")
            current_loc = os.path.join(current_source, "localization", "simp_chinese")
            candidate_loc = os.path.join(candidate_source, "localization", "simp_chinese")
            os.makedirs(current_loc)
            os.makedirs(candidate_loc)
            with open(
                os.path.join(current_source, ".remis_project.json"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write('{"config": {"translation_dirs": ["C:/translations"]}}')
            with open(
                os.path.join(current_loc, "old_l_simp_chinese.yml"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write('l_simp_chinese:\\n old:0 "旧"\\n')
            with open(
                os.path.join(candidate_loc, "new_l_simp_chinese.yml"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write('l_simp_chinese:\\n new:0 "新"\\n')

            mock_obj = MagicMock()
            mock_obj.model_dump.return_value = {
                "project_id": "managed-project",
                "name": "Managed Project",
                "game_id": "victoria3",
                "source_path": current_source,
            }
            self.mock_repo.get_project.return_value = mock_obj
            self.pm.refresh_project_files = AsyncMock()
            self.pm.log_history_event = AsyncMock()

            with patch(
                "scripts.core.project_manager.SOURCE_DIR",
                managed_root,
            ):
                result = await self.pm.promote_incremental_source(
                    "managed-project",
                    candidate_source,
                )

            self.assertEqual(result["mode"], "managed_copy")
            self.assertEqual(
                result["source_path"],
                os.path.realpath(current_source),
            )
            self.assertFalse(
                os.path.exists(
                    os.path.join(current_loc, "old_l_simp_chinese.yml")
                )
            )
            self.assertTrue(
                os.path.exists(
                    os.path.join(current_loc, "new_l_simp_chinese.yml")
                )
            )
            self.assertTrue(
                os.path.exists(
                    os.path.join(current_source, ".remis_project.json")
                )
            )
            self.mock_repo.update_project_source_path.assert_not_awaited()
            self.mock_repo.touch_project.assert_awaited_once_with(
                "managed-project"
            )
            self.pm.refresh_project_files.assert_awaited_once_with(
                "managed-project"
            )
            self.pm.log_history_event.assert_awaited_once()

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

    async def test_run_incremental_update_workflow_advances_successful_custom_source(self):
        project_id = "workflow-source-advance"
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = {
            "project_id": project_id,
            "source_language": "en",
            "game_id": "victoria3",
        }
        self.mock_repo.get_project.return_value = mock_obj
        self.pm.promote_incremental_source = AsyncMock(return_value={
            "mode": "managed_copy",
            "source_path": "C:/managed/demo",
            "selected_source_path": "C:/fixtures/new-version",
        })

        config = MagicMock()
        config.project_id = project_id
        config.target_lang_codes = [MagicMock(value="zh-CN")]
        config.api_provider = "test-provider"
        config.provider = None
        config.model = "test-model"
        config.batch_size_limit = None
        config.concurrency_limit = None
        config.rpm_limit = None
        config.dry_run = False
        config.custom_source_path = "C:/fixtures/new-version"
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
            mock_run.return_value = {
                "status": "success",
                "output_dir": "C:/outputs/update",
            }

            result = await self.pm.run_incremental_update_workflow(config)

        self.pm.promote_incremental_source.assert_awaited_once_with(
            project_id,
            "C:/fixtures/new-version",
        )
        self.assertEqual(
            result["source_advancement"]["selected_source_path"],
            "C:/fixtures/new-version",
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
