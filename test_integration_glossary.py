import sys
import os
import logging
from typing import List, Dict

# Ensure project root is in path
sys.path.append(os.path.abspath('.'))

from scripts import app_settings
from scripts.workflows import initial_translate
from scripts.core.glossary_manager import glossary_manager
from scripts.utils import i18n
from scripts.core.api_handler import get_handler
from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_processor import BatchTask

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SimpleMockHandler(BaseApiHandler):
    def initialize_client(self): return "mock"
    def _call_api(self, client, prompt): return "Translated Text"
    def translate_batch(self, task: BatchTask) -> BatchTask:
        prompt = self._build_prompt(task)
        # Check for injection
        if "CRITICAL GLOSSARY INSTRUCTIONS" in prompt:
            print("\n[VERIFICATION] SUCCESS: Glossary found in prompt!")
        else:
            print("\n[VERIFICATION] FAILURE: Glossary NOT found in prompt.")
        
        task.translated_texts = ["Translation" for _ in task.texts]
        return task

def test_integration():
    # 1. Setup minimal requirements for initial_translate.run
    game_profile = {
        "id": "eu5",
        "name": "EU5",
        "encoding": "utf-8-sig",
        "strip_pl_diacritics": False,
        "source_localization_folder": "localization",
        "prompt_template": "Translate from {source_lang_name} to {target_lang_name}.",
        "format_prompt": "Format: {numbered_list}",
        "single_prompt_template": "...",
        "official_tags_codex": None
    }
    
    from scripts.app_settings import LANGUAGES
    source_lang = LANGUAGES["1"] # English
    target_languages = [LANGUAGES["2"]] # Simplified Chinese
    
    # Path to the EU5 demo mod
    override_path = os.path.join(os.path.abspath('.'), "source_mod", "Test_Project_Remis_EU5")
    
    # Mock the handler factory by patching the module function
    import scripts.core.api_handler
    scripts.core.api_handler.get_handler = lambda provider_name, model_name=None: SimpleMockHandler(provider_name)

    print("\n--- STARTING INTEGRATION TEST ---\n")
    try:
        initial_translate.run(
            mod_name="Test_Project_Remis_EU5",
            game_profile=game_profile,
            source_lang=source_lang,
            target_languages=target_languages,
            selected_provider="mock",
            mod_context="Integration Test",
            selected_glossary_ids=[15], # The EU5 glossary ID 15
            use_glossary=True,
            override_path=override_path
        )
    except Exception as e:
        print(f"Error during run: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n--- INTEGRATION TEST FINISHED ---\n")

if __name__ == "__main__":
    test_integration()
