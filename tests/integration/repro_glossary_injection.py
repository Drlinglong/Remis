import logging
import sys
import threading
from typing import Any, List, Dict

# Setup logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from scripts.core.glossary_manager import glossary_manager
from scripts.core.parallel_processor import ParallelProcessor, FileTask, BatchTask
from scripts.core.base_handler import BaseApiHandler

# Mock Handler to intercept prompt building
class MockHandler(BaseApiHandler):
    def initialize_client(self):
        return "mock_client"
    
    def _call_api(self, client: any, prompt: str) -> str:
        # Check if terms are injected in prompt
        if "GLOSSARY" in prompt or "Aeterna Roma" in prompt or "永恒罗马" in prompt:
            logging.info("SUCCESS: Glossary terms found in prompt!")
            logging.info(f"Prompt snippet: {prompt[:300]}...")
        else:
            logging.error("FAILURE: Glossary terms NOT found in prompt.")
            logging.info(f"Prompt snippet: {prompt[:300]}...")
        return "Mock Response"

    def translate_batch(self, task: BatchTask) -> BatchTask:
         # Override to use our logic without network calls
         prompt = self._build_prompt(task)
         # Assume success
         task.translated_texts = ["Translated " + t for t in task.texts]
         return task

def repro_run():
    logging.info("Starting Reproduction Script")
    
    # 1. Load Glossary for EU5
    game_id = "eu5"
    if glossary_manager.load_game_glossary(game_id):
        logging.info(f"Glossary loaded. Entries: {len(glossary_manager.in_memory_glossary.get('entries', []))}")
    else:
        logging.error("Failed to load glossary.")
        return

    # Verify Glossary Content
    entries = glossary_manager.in_memory_glossary.get('entries', [])
    if entries:
        logging.info(f"First entry translation: {entries[0].get('translations')}")

    # 2. Prepare Task Data
    source_lang = {"code": "en", "name": "English"}
    target_lang = {"code": "zh-CN", "name": "Simplified Chinese", "custom_name": "Simplified Chinese"}
    game_profile = {
        "id": "eu5", 
        "prompt_template": "Translate from {source_lang_name} to {target_lang_name}.", 
        "official_tags_codex": None,
        "single_prompt_template": "Translate {source_lang_name} to {target_lang_name}: {raw_text}", # Just in case
        "id": "eu5" # Ensure ID is set
    }
    
    text_with_term = "This is a test for Aeterna Roma and Solidus Nova."
    
    file_task = FileTask(
        filename="test_file.txt",
        root="D:/test",
        original_lines=[],
        texts_to_translate=[text_with_term],
        key_map={},
        is_custom_loc=False,
        target_lang=target_lang,
        source_lang=source_lang,
        game_profile=game_profile,
        mod_context="EU5 Test",
        provider_name="mock",
        output_folder_name="out",
        source_dir="src",
        dest_dir="dst",
        client=None,
        mod_name="test_mod"
    )

    # 3. Process with ParallelProcessor
    handler = MockHandler("mock")
    processor = ParallelProcessor(max_workers=2) # Use threads

    def translation_func(batch_task):
        # This runs in a worker thread
        # logging.info(f"Worker Thread: Checking glossary state... Entries: {len(glossary_manager.in_memory_glossary.get('entries', []))}")
        return handler.translate_batch(batch_task)

    logging.info("Starting parallel processing...")
    file_results, warnings = processor.process_files_parallel([file_task], translation_func)
    
    logging.info("Processing finished.")

if __name__ == "__main__":
    repro_run()
