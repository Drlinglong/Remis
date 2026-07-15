from unittest.mock import MagicMock

from scripts.core.agents.translation_fixer_agent import TranslationFixerAgent
from scripts.core.parallel_types import BatchTask, FileTask


def test_fixer_uses_handler_and_returns_structured_response():
    handler = MagicMock()
    handler.client = MagicMock()
    handler._call_api.return_value = '["Fixed"]'

    file_task = MagicMock(spec=FileTask)
    file_task.target_lang = {"name": "Russian", "code": "ru"}

    batch_task = MagicMock(spec=BatchTask)
    batch_task.file_task = file_task
    batch_task.texts = ["Source"]
    batch_task.batch_index = 0
    batch_task.start_index = 0

    warning = MagicMock()
    warning.level.value = "error"
    warning.line_number = 1
    warning.message = "Error"
    warning.details = "Details"

    fixer = TranslationFixerAgent(handler)
    success, fixed_texts = fixer.attempt_fix(batch_task, ["Broken"], [warning])

    assert success is True
    assert fixed_texts == ["Fixed"]
    handler._call_api.assert_called_once()
    assert handler._call_api.call_args.args[0] is handler.client
