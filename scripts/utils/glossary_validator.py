# scripts/utils/glossary_validator.py
import logging
import re
from typing import List, Dict, Any

from scripts.utils import i18n
# Assuming BatchTask is available from scripts.core.parallel_processor
# We will handle the exact import path later if needed.
from scripts.core.parallel_types import BatchTask

class GlossaryValidator:
    """
    Validates translation consistency against a glossary.
    """

    def _get_pattern_for_lang(self, term: str, lang_code: str) -> str:
        """根据语言代码，为术语生成合适的正则表达式模式。"""
        is_cjk = any(lang in lang_code for lang in ['zh', 'ja', 'ko'])
        if is_cjk:
            return re.escape(term)
        else:
            return r'\b' + re.escape(term) + r'\b'

    def validate_batch(self, task: BatchTask, glossary: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Validates a batch of translations against the glossary.

        Args:
            task (BatchTask): The batch task containing original and translated texts.
            glossary (Dict[str, str]): The glossary to validate against.

        Returns:
            List[Dict[str, Any]]: A list of warnings for inconsistencies.
        """
        warnings = []
        if not hasattr(task, 'translated_texts') or not task.translated_texts:
            return warnings

        original_chunk = "\n".join(task.texts)
        translated_chunk = "\n".join(task.translated_texts)

        file_path = task.file_task.filename
        batch_id = task.batch_index

        target_lang_code = task.file_task.target_lang.get("code", "").lower()
        source_lang_code = task.file_task.source_lang.get("code", "").lower()

        for source_term, target_term in glossary.items():
            try:
                source_pattern = self._get_pattern_for_lang(source_term, source_lang_code)
                target_pattern = self._get_pattern_for_lang(target_term, target_lang_code)

                source_count = len(re.findall(source_pattern, original_chunk, re.IGNORECASE))
                translated_count = len(re.findall(target_pattern, translated_chunk, re.IGNORECASE))
            except re.error as e:
                logging.warning(f"Skipping glossary term due to regex error: {e}")
                continue

            if source_count > 0 and source_count != translated_count:
                warnings.append({
                    "level": "warning",
                    "file_path": file_path,
                    "batch_id": batch_id,
                    "source_term": source_term,
                    "target_term": target_term,
                    "source_count": source_count,
                    "translated_count": translated_count,
                    "message": i18n.t(
                        "glossary_validator_warning",
                        file_path=file_path,
                        batch_id=batch_id + 1,
                        source_term=source_term,
                        source_count=source_count,
                        target_term=target_term,
                        translated_count=translated_count
                    )
                })

        return warnings

# Example usage (for testing purposes)
if __name__ == '__main__':
    # This is a mock setup for testing the validator logic.
    i18n.load_language('zh_CN')  # Load translations for testing
    print("--- Running Validator Self-Tests ---")

    # Mock FileTask
    class MockFileTask:
        def __init__(self, filename, source_lang, target_lang):
            self.filename = filename
            self.source_lang = source_lang
            self.target_lang = target_lang

    # Mock Glossary
    mock_glossary = {
        "convoy": "船队",
        "fleet": "舰队"
    }

    validator = GlossaryValidator()

    # --- Test Case 1: Non-CJK to CJK (e.g., English to Chinese) ---
    print("\n[Test Case 1: EN -> ZH (CJK)]")
    mock_file_task_cjk = MockFileTask(
        "en_to_zh.yml",
        source_lang={"code": "en-US"},
        target_lang={"code": "zh-CN"}
    )
    mock_batch_task_cjk = BatchTask(
        file_task=mock_file_task_cjk,
        batch_index=0,
        start_index=0,
        end_index=2,
        texts=["A single convoy.", "The whole fleet is here."]
    )

    # 1a: Incorrect CJK translation (should trigger warnings)
    print("1a: Testing incorrect CJK translation...")
    mock_batch_task_cjk.translated_texts = ["一个护卫舰。", "整个舰队都在这里。"]
    validation_warnings_cjk_fail = validator.validate_batch(mock_batch_task_cjk, mock_glossary)
    if validation_warnings_cjk_fail:
        print("  PASSED: Correctly detected inconsistency.")
        for warning in validation_warnings_cjk_fail:
            print(f"    - {warning['message']}")
    else:
        print("  FAILED: Did not detect inconsistency.")

    # 1b: Correct CJK translation (should NOT trigger warnings)
    print("\n1b: Testing correct CJK translation...")
    mock_batch_task_cjk.translated_texts = ["一个船队。", "整个舰队都在这里。"]
    validation_warnings_cjk_pass = validator.validate_batch(mock_batch_task_cjk, mock_glossary)
    if not validation_warnings_cjk_pass:
        print("  PASSED: Correctly validated translation.")
    else:
        print("  FAILED: Incorrectly flagged a valid translation.")
        for warning in validation_warnings_cjk_pass:
            print(f"    - {warning['message']}")


    # --- Test Case 2: Non-CJK to Non-CJK (e.g., English to Polish) ---
    print("\n[Test Case 2: EN -> PL (Non-CJK)]")
    mock_file_task_non_cjk = MockFileTask(
        "en_to_pl.yml",
        source_lang={"code": "en-US"},
        target_lang={"code": "pl-PL"}
    )
    mock_batch_task_non_cjk = BatchTask(
        file_task=mock_file_task_non_cjk,
        batch_index=0,
        start_index=0,
        end_index=2,
        texts=["The convoy is ready.", "Fleet is preparing."]
    )
    mock_glossary_pl = {"convoy": "konwój", "fleet": "flota"}

    # 2a: Correct Non-CJK translation
    print("2a: Testing correct Non-CJK translation...")
    mock_batch_task_non_cjk.translated_texts = ["konwój jest gotowy.", "flota przygotowuje się."]
    validation_warnings_non_cjk_pass = validator.validate_batch(mock_batch_task_non_cjk, mock_glossary_pl)
    if not validation_warnings_non_cjk_pass:
        print("  PASSED: Correctly validated translation (with word boundaries).")
    else:
        print("  FAILED: Incorrectly flagged a valid translation.")

    # 2b: Incorrect Non-CJK translation (partial match, should be ignored by \b)
    print("\n2b: Testing incorrect Non-CJK translation (partial match)...")
    mock_batch_task_non_cjk.translated_texts = ["Ten konwojent jest gotowy.", "flota przygotowuje się."] # konwojent contains konwój
    validation_warnings_non_cjk_fail = validator.validate_batch(mock_batch_task_non_cjk, mock_glossary_pl)
    if validation_warnings_non_cjk_fail:
        print("  PASSED: Correctly detected inconsistency (partial match was ignored).")
    else:
        print("  FAILED: Did not detect inconsistency.")

    print("\n--- Self-Tests Finished ---")
