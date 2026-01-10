import unittest
from unittest.mock import MagicMock, patch, ANY
import os
import shutil
from scripts.core.project_manager import ProjectManager

class TestProjectManager(unittest.TestCase):
    
    def setUp(self):
        # 1. Mock Dependencies
        self.mock_file_service = MagicMock()
        self.mock_repo = MagicMock()
        self.mock_kanban = MagicMock()
        
        # 2. Instantiate ProjectManager with Injected Mocks
        self.pm = ProjectManager(
            file_service=self.mock_file_service,
            project_repository=self.mock_repo,
            kanban_service=self.mock_kanban,
            db_path=":memory:" # Valid but unused since we mock repo
        )

    @patch("scripts.core.project_manager.ProjectJsonManager")
    @patch("scripts.core.project_manager.os.path.exists")
    @patch("scripts.core.project_manager.shutil.copytree")
    def test_create_project_success(self, mock_copy, mock_exists, mock_json_mgr):
        """
        Test creating a project successfully invokes repository and file service.
        """
        # Setup
        # Assume folder IS inside source_dir (mock_exists=True for simplified path check logic)
        # Actually ProjectManager checks if startswith SOURCE_DIR. 
        # We need to mock os.path.abspath too if we want precision, but let's trust the logic structure.
        
        # Configure os.path.exists to return False to avoid infinite loop in folder collision check
        mock_exists.return_value = False
        
        # Mock Repository returning a valid Project object (as dict or obj)
        mock_pydantic_proj = MagicMock()
        mock_pydantic_proj.model_dump.return_value = {"id": "123", "name": "TestProj"}
        self.mock_repo.create_project.return_value = mock_pydantic_proj
        
        # Actions
        result = self.pm.create_project(
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
        # This indirectly calls file_service.scan_and_sync_files
        self.mock_file_service.scan_and_sync_files.assert_called_once()
        
        self.assertEqual(result["id"], "123")

    def test_refresh_project_files_delegation(self):
        """
        Test that refresh_project_files correctly delegates to FileService.
        """
        # Setup
        project_id = "test-123"
        mock_proj_data = {"id": project_id, "name": "Test", "source_path": "/path/to/source"}
        
        # Mock self.get_project (which calls repo.get_project)
        # Since get_project returns model_dump(), we need repo.get_project to return an object with model_dump
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = mock_proj_data
        self.mock_repo.get_project.return_value = mock_obj

        # Patch ProjectJsonManager to avoid disk I/O for translation_dirs
        with patch("scripts.core.project_manager.ProjectJsonManager") as MockJson:
            MockJson.return_value.get_config.return_value = {"translation_dirs": ["/trans/path"]}
            
            # Action
            self.pm.refresh_project_files(project_id)
            
            # Assertion
            self.mock_file_service.scan_and_sync_files.assert_called_once_with(
                project_id, 
                "/path/to/source", 
                ["/trans/path"], 
                "Test"
            )

    def test_update_project_metadata(self):
        """
        Verify metadata update flows to repository calls correctly.
        """
        project_id = "test-meta"
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = {"id": project_id, "source_path": "/dummy"}
        self.mock_repo.get_project.return_value = mock_obj
        
        with patch("scripts.core.project_manager.ProjectJsonManager"):
            self.pm.update_project_metadata(project_id, "stellaris", "english")
        
        # Assert aliases handled ("stellaris" -> "stellaris")
        self.mock_repo.update_project_metadata.assert_called_once_with(
            project_id, "stellaris", "english"
        )

if __name__ == '__main__':
    unittest.main()
