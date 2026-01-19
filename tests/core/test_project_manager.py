import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import shutil
from scripts.core.project_manager import ProjectManager

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

if __name__ == '__main__':
    unittest.main()
