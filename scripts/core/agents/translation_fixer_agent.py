# scripts/core/agents/translation_fixer_agent.py
import logging
from typing import List, Dict, Any, Optional, Tuple

from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_types import BatchTask
from scripts.utils import i18n
from scripts.utils.structured_parser import parse_response
from scripts.core.schemas import TranslationResponse

logger = logging.getLogger(__name__)

class TranslationFixerAgent:
    """
    Agent responsible for automatically fixing generic translation formats based on validation errors.
    It takes the original text, the broken translation, and the specific error messages from the Validator,
    and prompts the LLM to provide a corrected version.
    """
    
    def __init__(self, handler: BaseApiHandler):
        """
        Initializes the fixer with an existing handler instance to reuse the same provider/model.
        """
        self.handler = handler
        self.logger = logging.getLogger(__name__)

    def _build_fix_prompt(self, task: BatchTask, broken_translations: List[str], error_reports: Dict[int, List[Any]]) -> str:
        """
        Builds a highly constrained prompt focused entirely on bug fixing.
        """
        source_texts = task.texts
        target_lang_name = task.file_task.target_lang.get("custom_name", task.file_task.target_lang["name"]) if task.file_task.target_lang.get("is_shell") else task.file_task.target_lang["name"]
        
        # Construct the error report
        error_context = []
        for i in range(len(source_texts)):
            # Line number is 1-indexed relative to the batch if we just use index
            # But the validator uses absolute line_number. 
            # In parallel_processor, we pass start_line=task.start_index + 1
            line_num = task.start_index + 1 + i
            
            # Find errors for this specific line
            line_errors = error_reports.get(line_num, [])
            
            if line_errors:
                error_msgs = " | ".join([err.message + (" (" + err.details + ")" if err.details else "") for err in line_errors])
                error_context.append(f"Item {i+1}:\n  Source: {source_texts[i]}\n  Bad Translation ({target_lang_name}): {broken_translations[i]}\n  Errors Found: {error_msgs}\n")
            else:
                # If a line had no errors, instruct the LLM to just repeat the good translation
                error_context.append(f"Item {i+1} (VALID - DO NOT CHANGE):\n  Source: {source_texts[i]}\n  Current Translation: {broken_translations[i]}\n")
                
        error_block = "\n".join(error_context)
        
        prompt = (
            f"You are a strict Localization Quality Assurance Engineer. A previous AI translation to {target_lang_name} failed technical validation.\n"
            "Your task is to FIX the formatting errors in the 'Bad Translation' while preserving the translated meaning as much as possible.\n\n"
            "CRITICAL RULES:\n"
            "1. ONLY fix the errors explicitly listed below.\n"
            "2. Ensure exact parity of special variables (e.g. $pop$, [Concept('...', '...'), [SCOPE.etc]) between Source and Translation.\n"
            "3. Ensure all color/formatting tags (e.g. #variable, §Y) are properly paired and spaced if required.\n"
            "4. For items marked '(VALID - DO NOT CHANGE)', you MUST return the EXACT 'Current Translation' as provided. Do not modify valid items.\n\n"
            "--- ERROR REPORT ---\n"
            f"{error_block}\n"
            "--------------------\n\n"
            f"You must return the corrected translations in exactly the same length ({len(source_texts)} items) as a JSON Array of strings:\n"
            '[\n  "fixed translation 1",\n  "fixed translation 2"\n]\n'
        )
        return prompt

    def attempt_fix(self, task: BatchTask, broken_translations: List[str], validation_warnings: List[Any], max_retries: int = 2) -> Tuple[bool, List[str]]:
        """
        Attempts to fix the broken translations.
        Returns a tuple: (success_boolean, corrected_translations_list)
        
        Note: The validation_warnings are flat. We need to map them back to their line index.
        """
        batch_num = task.batch_index + 1
        
        # Group warnings by line_number (which corresponds to task.start_index + 1 + i)
        error_reports = {}
        for warn in validation_warnings:
            # warn level check using value because Enum Serialization
            level_val = warn.level.value if hasattr(warn.level, 'value') else warn.level
            if level_val == 'error':
                ln = warn.line_number
                if ln not in error_reports:
                    error_reports[ln] = []
                error_reports[ln].append(warn)
                
        if not error_reports:
            self.logger.info(f"Agent Fixer called for batch {batch_num}, but no ERROR level warnings found. Passing original.")
            return True, broken_translations
            
        self.logger.warning(i18n.t("agent_fixer_engaged", batch_num=batch_num, error_count=len(validation_warnings)))
        
        current_broken = broken_translations
        
        for attempt in range(max_retries):
            self.logger.info(f"Agent Fixer Attempt {attempt + 1}/{max_retries} for Batch {batch_num}...")
            prompt = self._build_fix_prompt(task, current_broken, error_reports)
            
            try:
                raw_response = self.handler._call_api(self.handler.client, prompt)
                fixed_texts = parse_response(raw_response, TranslationResponse, task.file_task.target_lang["code"])
                
                if fixed_texts and len(fixed_texts.translations) == len(task.texts):
                    # We have a valid structural response, but is it ACTUALLY fixed?
                    # The parallel_processor will re-validate it.
                    self.logger.info(f"Agent Fixer generated a new response for Batch {batch_num}.")
                    return True, fixed_texts.translations
                else:
                    self.logger.error(f"Agent Fixer returned invalid structure (Expected {len(task.texts)} items).")
            except Exception as e:
                self.logger.error(f"Agent Fixer call failed: {e}")
                
        self.logger.error(f"Agent Fixer failed to resolve issues after {max_retries} attempts.")
        return False, current_broken
