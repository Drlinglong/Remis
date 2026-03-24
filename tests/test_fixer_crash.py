# tests/test_fixer_crash.py
from unittest.mock import MagicMock
from scripts.core.agents.translation_fixer_agent import TranslationFixerAgent
from scripts.core.parallel_types import BatchTask, FileTask

def test_fixer_crash():
    # Mock an OpenAI client (which is what file_task.client currently is)
    mock_client = MagicMock()
    # Mock a FileTask
    mock_file_task = MagicMock(spec=FileTask)
    mock_file_task.client = mock_client
    mock_file_task.target_lang = {"name": "Russian", "code": "ru"}
    
    # Mock a BatchTask
    mock_batch_task = MagicMock(spec=BatchTask)
    mock_batch_task.file_task = mock_file_task
    mock_batch_task.texts = ["Source"]
    mock_batch_task.batch_index = 0
    mock_batch_task.start_index = 0
    
    # Initialize Fixer with the client (current behavior)
    fixer = TranslationFixerAgent(mock_file_task.client)
    
    print("Attempting fix with client...")
    try:
        # Mock validation warnings
        mock_warn = MagicMock()
        mock_warn.level.value = 'error'
        mock_warn.line_number = 1
        mock_warn.message = "Error"
        mock_warn.details = "Details"
        
        fixer.attempt_fix(mock_batch_task, ["Broken"], [mock_warn])
    except AttributeError as e:
        print(f"CRASHED as expected: {e}")
    except Exception as e:
        print(f"Failed with unexpected error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_fixer_crash()
