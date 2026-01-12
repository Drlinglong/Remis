import pytest
import os
import shutil
from unittest.mock import MagicMock, patch

from scripts.app_settings import SOURCE_DIR, DEST_DIR
from pydantic import BaseModel

class CustomLangConfig(BaseModel):
    name: str
    code: str
    key: str
    folder_prefix: str

# Mock data
MOCK_PROJECT_NAME = "TestProject_EnglishDisguise"
MOCK_GAME_ID = "victoria3"

@pytest.fixture
def setup_teardown():
    # Setup: Create a dummy source mod
    os.environ["GEMINI_API_KEY"] = "dummy_key" # Set dummy key for test
    source_path = os.path.join(SOURCE_DIR, MOCK_PROJECT_NAME)
    os.makedirs(os.path.join(source_path, "localization", "english"), exist_ok=True)
    with open(os.path.join(source_path, "localization", "english", "test_l_english.yml"), "w", encoding="utf-8-sig") as f:
        f.write("l_english:\n TEST_KEY:0 \"Test Value\"\n")
    
    yield
    
    # Teardown: Cleanup source and dest
    # We clean up everything that starts with IT- or it- to be safe
    for folder in os.listdir(DEST_DIR):
        if folder.lower().startswith("it-"):
            shutil.rmtree(os.path.join(DEST_DIR, folder), ignore_errors=True)
            
    if os.path.exists(source_path):
        shutil.rmtree(source_path)

def test_english_disguise_configuration(setup_teardown):
    """
    Test that the English Disguise configuration correctly:
    1. Sets the output folder prefix.
    2. Sets the internal language key to 'l_english'.
    3. Uses the 'Real' language name for the AI prompt.
    """
    
    # Define Custom Config for "Italian disguised as English"
    custom_config = CustomLangConfig(
        name="Italian",       # Real language for AI
        code="custom",
        key="l_english",      # Disguise key (Game sees English)
        folder_prefix="IT-"   # Output folder prefix
    )
    
    # Define paths
    mod_root = os.path.join(SOURCE_DIR, MOCK_PROJECT_NAME)
    loc_root = os.path.join(mod_root, "localization")
    file_root = os.path.join(loc_root, "english")
    
    # Mock objects required by run()
    source_lang_obj = {"code": "en", "key": "l_english", "name": "English"}
    target_langs_obj = [{"code": "custom", "key": "l_english", "folder_prefix": "IT-", "name": "Italian"}] 
    game_profile_obj = {"id": "victoria3", "encoding": "utf-8-sig", "source_localization_folder": "localization"}

    # Import locally to avoid scope issues
    import scripts.workflows.initial_translate as it_module
    from scripts.workflows.initial_translate import run

    # Mock the actual AI translation to avoid API calls
    # We patch the ParallelProcessor.process_files_stream method
    with patch("scripts.core.parallel_processor.ParallelProcessor.process_files_stream") as mock_process:
        # Create a dummy FileTask to return
        dummy_file_task = MagicMock()
        dummy_file_task.filename = "test_l_english.yml"
        dummy_file_task.path = os.path.join(file_root, "test_l_english.yml")
        dummy_file_task.source_lang = {"code": "en", "key": "l_english"}
        dummy_file_task.target_lang = {"code": "custom", "folder_prefix": "IT-", "key": "l_english"} 
        dummy_file_task.game_profile = {"encoding": "utf-8-sig"}
        dummy_file_task.root = file_root
        dummy_file_task.loc_root = loc_root
        dummy_file_task.mod_name = MOCK_PROJECT_NAME
        dummy_file_task.is_custom_loc = False
        
        # Mock return value: Generator yielding (file_task, translated_texts, warnings, is_failed)
        mock_process.return_value = iter([(dummy_file_task, ["l_english:\n TEST_KEY:0 \"Valore di prova\"\n"], [], False)])
        
        # Mock discover_files to ensure run() proceeds past the check
        with patch("scripts.workflows.initial_translate.discover_files") as mock_discover:
            mock_discover.return_value = [{
                "path": os.path.join(file_root, "test_l_english.yml"), 
                "filename": "test_l_english.yml", 
                "root": file_root, 
                "texts_to_translate": ["text"], 
                "original_lines": [], 
                "key_map": [], 
                "is_custom_loc": False,
                "loc_root": loc_root
            }]
            
            # Mock archive_manager to prevent early exit
            with patch("scripts.workflows.initial_translate.archive_manager") as mock_archive:
                mock_archive.get_or_create_mod_entry.return_value = 1
                mock_archive.create_source_version.return_value = 1
                
                # Mock other handlers to prevent side effects or errors
                with patch("scripts.workflows.initial_translate.directory_handler"), \
                     patch("scripts.workflows.initial_translate.asset_handler"), \
                     patch("scripts.workflows.initial_translate.api_handler") as mock_api_handler, \
                     patch("scripts.workflows.initial_translate.file_parser") as mock_file_parser:
                     
                    mock_handler = MagicMock()
                    mock_handler.client = MagicMock()
                    mock_handler.provider_name = "gemini"
                    mock_api_handler.get_handler.return_value = mock_handler
                    
                    # Mock file parser to avoid reading dummy file from disk
                    mock_file_parser.extract_translatable_content.return_value = ([], ["text"], {})

                    # Mock file builder to verify output path logic without writing to disk
                    with patch("scripts.core.file_builder.rebuild_and_write_file") as mock_build:
                        # [FIX] In the actual implementation, prefix is applied TO the slugified name.
                        # output_folder_name = f"{prefix}{slugify_to_ascii(mod_name)}"
                        # So for IT- and TestProject, it becomes IT-testproject_englishdisguise
                        from scripts.utils.system_utils import slugify_to_ascii
                        sanitized_name = slugify_to_ascii(MOCK_PROJECT_NAME)
                        expected_output_folder = os.path.join(DEST_DIR, "IT-" + sanitized_name)
                        
                        expected_file_path = os.path.join(expected_output_folder, "localization", "english", "test_l_english.yml")
                        mock_build.return_value = expected_file_path
                
                        run(
                            mod_name=MOCK_PROJECT_NAME,
                            source_lang=source_lang_obj,
                            target_languages=target_langs_obj,
                            game_profile=game_profile_obj,
                            mod_context="",
                            selected_glossary_ids=[],
                            model_name="gemini-pro",
                            use_glossary=True,
                            custom_lang_config=custom_config.dict()
                        )
            
                        # Assertions
                        
                        # Verify rebuild_and_write_file was called
                        assert mock_build.called, "file_builder.rebuild_and_write_file was not called."
                        
                        # Verify arguments
                        call_args = mock_build.call_args
                        
                        # Check dest_dir
                        actual_dest_dir = call_args[0][4]
                        expected_dest_dir = os.path.join(expected_output_folder, "localization", "english")
                        
                        # Normalize paths for comparison
                        assert os.path.normpath(actual_dest_dir) == os.path.normpath(expected_dest_dir), \
                            f"Expected dest_dir {expected_dest_dir}, got {actual_dest_dir}"
                            
                        # Check target_lang has correct key
                        actual_target_lang = call_args[0][7]
                        assert actual_target_lang["key"] == "l_english", "Target language key passed to builder should be 'l_english'"

if __name__ == "__main__":
    pytest.main([__file__])
