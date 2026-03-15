import unittest
import os
import shutil
import tempfile
import time
from typing import List, Dict, Any
from unittest.mock import MagicMock, patch

# Adjust path to allow imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.parallel_types import FileTask, BatchTask
from scripts.core.parallel_processor import ParallelProcessor

class TestCheckpointManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_save_and_load(self):
        self.manager.mark_file_completed("file1.txt")
        self.assertTrue(self.manager.is_file_completed("file1.txt"))
        self.assertFalse(self.manager.is_file_completed("file2.txt"))

        # Reload
        new_manager = CheckpointManager(self.test_dir)
        self.assertTrue(new_manager.is_file_completed("file1.txt"))
        self.assertFalse(new_manager.is_file_completed("file2.txt"))

    def test_clear_checkpoint(self):
        self.manager.mark_file_completed("file1.txt")
        self.assertTrue(os.path.exists(self.manager.checkpoint_path))
        self.manager.clear_checkpoint()
        self.assertFalse(os.path.exists(self.manager.checkpoint_path))

class TestParallelProcessorStreaming(unittest.TestCase):
    def setUp(self):
        self.processor = ParallelProcessor(max_workers=2)

    def test_process_files_stream(self):
        # Mock FileTasks
        tasks = []
        for i in range(3):
            task = MagicMock(spec=FileTask)
            task.filename = f"file_{i}.txt"
            task.texts_to_translate = [f"text_{i}_{j}" for j in range(10)]
            task.provider_name = "mock"
            tasks.append(task)

        # Mock translation function
        def mock_translate(batch_task, **kwargs):
            batch_task.translated_texts = [f"translated_{t}" for t in batch_task.texts]
            return batch_task

        # Generator
        def task_generator():
            for t in tasks:
                yield t

        # Run stream
        results = []
        stream = self.processor.process_files_stream(task_generator(), mock_translate)
        
        for file_task, translated_texts, warnings in stream:
            results.append((file_task.filename, translated_texts))

        self.assertEqual(len(results), 3)
        
        # Verify content
        for filename, texts in results:
            self.assertTrue(filename.startswith("file_"))
            self.assertEqual(len(texts), 10)
            self.assertTrue(texts[0].startswith("translated_text_"))

if __name__ == '__main__':
    unittest.main()
