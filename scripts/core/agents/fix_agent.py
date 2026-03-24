import logging
from typing import List, Dict, Any, Optional, Tuple
import re

from scripts.core.base_handler import BaseApiHandler
from scripts.utils.post_process_validator import PostProcessValidator
from scripts.config.validators.hoi4_rules import RULES as HOI4_RULES
from scripts.config.validators.vic3_rules import RULES as VIC3_RULES

logger = logging.getLogger(__name__)

class ReflexionFixAgent:
    """
    A specialized agent for the Agent Workshop that uses a Reflexion-style workflow:
    1. Reflection: Analyze the error and identify the violation.
    2. Suggestion: Propose a corrected string.
    3. Verification: Perform parity checks on technical tags.
    """
    
    def __init__(self, handler: BaseApiHandler):
        self.handler = handler
        self.logger = logging.getLogger(__name__)

    async def fix_issue(self, source: str, target: str, error_type: str, details: str, game_id: str = "hoi4") -> Dict[str, Any]:
        """
        Main entry point for fixing a single issue.
        """
        # 1. Reflection Phase
        reflection = await self._reflect(source, target, error_type, details)
        
        # 2. Fix Phase
        suggested_fix = await self._suggest_fix(source, target, reflection, game_id)
        
        # 3. Parity Check
        parity_passed, parity_msg = self._check_parity(source, suggested_fix)
        
        status = "SUCCESS" if parity_passed else "WARNING"
        
        return {
            "suggested_fix": suggested_fix,
            "reflection": reflection,
            "status": status,
            "parity_message": parity_msg
        }

    async def _reflect(self, source: str, target: str, error_type: str, details: str) -> str:
        prompt = (
            "You are a Localization QA Specialist. Analyze the following translation error.\n\n"
            f"Source Text: {source}\n"
            f"Translated Text (Broken): {target}\n"
            f"Error Type: {error_type}\n"
            f"Details: {details}\n\n"
            "Explain exactly why this is a violation of game localization rules. "
            "Focus on technical tags ($ $, [ ], #, §) and character encoding. "
            "Be concise."
        )
        response = await self.handler.generate_response(prompt)
        return response.strip()

    async def _suggest_fix(self, source: str, target: str, reflection: str, game_id: str) -> str:
        prompt = (
            "Based on your analysis, provide a FIXED version of the translation.\n\n"
            f"Source Text: {source}\n"
            f"Broken Text: {target}\n"
            f"Analysis: {reflection}\n\n"
            "Rules:\n"
            "1. Preserve the meaning of the translation.\n"
            "2. Ensure all technical tags are valid for the game engine.\n"
            "3. Return ONLY the corrected string, no extra text."
        )
        response = await self.handler.generate_response(prompt)
        # Basic cleanup: remove quotes if the LLM added them
        result = response.strip()
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        return result

    def _check_parity(self, source: str, target: str) -> Tuple[bool, str]:
        """
        Ensures that technical tags in the source are present in the target.
        """
        # Patterns for Paradox games
        patterns = [
            r"\$[^\$]+\$",        # $var$
            r"\[[^\]]+\]",        # [Concept]
            r"§[a-zA-Z]",         # §Y, §!
            r"#[a-zA-Z0-9_\.]+",   # #variable
        ]
        
        source_tags = []
        for p in patterns:
            source_tags.extend(re.findall(p, source))
            
        target_tags = []
        for p in patterns:
            target_tags.extend(re.findall(p, target))
            
        # Basic check: number of tags
        if len(source_tags) != len(target_tags):
            return False, f"Tag count mismatch: Source has {len(source_tags)}, Target has {len(target_tags)}"
            
        # Optional: check if specific tags exist (can be tricky if tags change slightly but remain valid)
        # For now, we trust the LLM if the count is right, but we flag if different.
        
        return True, "Parity check passed."
