import sys
import os
import logging
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.core.post_processing_manager import PostProcessingManager

def test_validation_log_capping():
    print("Testing PostProcessingManager log capping...")
    
    # Mock game profile and target lang
    game_profile = {"id": "hoi4", "name": "HOI4", "source_localization_folder": "localisation"}
    target_lang = {"code": "ru", "key": "l_russian", "name": "Russian"}
    
    # Create manager
    manager = PostProcessingManager(game_profile, "temp_output")
    
    # Simulate 100 errors for a single file
    results = []
    from scripts.utils.post_process_validator import ValidationResult, ValidationLevel
    for i in range(100):
        results.append(ValidationResult(
            is_valid=False,
            level=ValidationLevel.ERROR,
            message=f"Error {i}",
            line_number=i+1
        ))
    
    manager.validation_results["test_file.yml"] = results
    manager.files_with_issues = 1
    manager.total_files = 1
    
    # Capture logs
    logger = logging.getLogger("scripts.core.post_processing_manager")
    log_messages = []
    
    class TestHandler(logging.Handler):
        def emit(self, record):
            log_messages.append(record.getMessage())
            
    handler = TestHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    # Run log summary
    manager._log_validation_summary()
    
    # Verify count
    print(f"Total log messages captured: {len(log_messages)}")
    
    # Check if we have the "omitted from log" message
    found_truncation = any("omitted from log" in msg for msg in log_messages)
    print(f"Truncation message found: {found_truncation}")
    
    # Detailed log count (should be near MAX_DETAILED_LOGS = 50)
    # Each issue typically has 2 lines (file_issue and issue_details)
    # But our mock results only have message, so maybe 1+1 per issue.
    # Actually, it prints post_processing_file_issue and then post_processing_issue_details.
    
    assert found_truncation, "Should have found truncation message"
    assert len(log_messages) < 150, f"Too many log messages: {len(log_messages)}"

    print("Test PASSED!")

if __name__ == "__main__":
    test_validation_log_capping()
