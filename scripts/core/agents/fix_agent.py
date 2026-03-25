import logging
from typing import List, Dict, Any, Optional, Tuple
import re

from scripts.core.base_handler import BaseApiHandler
from scripts.core.base_handler import BaseApiHandler

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

    async def fix_issue_loop(self, source: str, target: str, error_type: str, details: str, game_id: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Runs the Reflexion workflow with up to max_retries, verifying against the PostProcessValidator.
        """
        from scripts.utils.post_process_validator import PostProcessValidator
        validator = PostProcessValidator()
        
        current_target = target
        current_error_type = error_type
        current_details = details
        
        reflection = ""
        suggested_fix = ""
        
        for attempt in range(max_retries):
            self.logger.info(f"Fix Attempt {attempt + 1}/{max_retries} for error: {current_error_type}")
            
            # 1. Reflect & Fix
            reflection = await self._reflect(source, current_target, current_error_type, current_details)
            suggested_fix = await self._suggest_fix(source, current_target, reflection, game_id)
            
            # 2. Validate using the robust validator mechanism
            results = validator.validate_entry(
                game_id=game_id,
                key="mock_key",
                value=suggested_fix,
                source_value=source
            )
            
            # Filter for Errors (we ignore warnings and info in this context, or maybe warnings too?)
            errors = [r for r in results if r.level.value == "error"]
            if not errors:
                self.logger.info("Validator passed. Fix successful.")
                return {
                    "suggested_fix": suggested_fix,
                    "reflection": reflection,
                    "status": "SUCCESS",
                    "parity_message": "Validation passed according to game rules."
                }
            
            # Prepare next iteration
            self.logger.warning(f"Validator failed on attempt {attempt + 1}. Updating prompts.")
            current_error_type = " | ".join([e.message for e in errors])
            current_details = " | ".join([e.details for e in errors if e.details])
            current_target = suggested_fix
            
        return {
            "suggested_fix": suggested_fix,
            "reflection": reflection,
            "status": "FAILED",
            "parity_message": f"Failed after {max_retries} attempts. Remaining errors: {current_error_type}."
        }

    async def fix_batch_loop(self, issues: List[Dict[str, Any]], game_id: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Runs the Reflexion workflow for a FULL BATCH of issues to save time and tokens.
        """
        import json
        from scripts.utils.post_process_validator import PostProcessValidator
        from scripts.utils.structured_parser import parse_response
        from scripts.core.schemas import TranslationResponse
        
        validator = PostProcessValidator()
        
        # current_state: tracking each issue's progress.
        # Active indices track which issues still need fixing.
        current_state = []
        for issue in issues:
            current_state.append({
                "source": issue["source_str"],
                "target": issue["target_str"],
                "error_messages": [issue["error_type"]],
                "error_details": [issue.get("details", "")],
                "is_fixed": False,
                "suggested_fix": "",
                "key": issue["key"],
                "file_name": issue["file_name"]
            })
            
        for attempt in range(max_retries):
            # 1. Filter out already fixed issues for the prompt
            active_indices = [i for i in range(len(current_state)) if not current_state[i]["is_fixed"]]
            if not active_indices:
                self.logger.info("All issues in batch fixed successfully!")
                break
                
            self.logger.info(f"Batch Fix Attempt {attempt + 1}/{max_retries} for {len(active_indices)} issues.")
            prompt = self._build_batch_prompt([current_state[i] for i in active_indices], game_id)
            
            try:
                # 2. Call LLM for the batch
                raw_response = self.handler._call_api(self.handler.client, prompt)
                
                # Use StructuredParser to ensure we get a clean list
                parsed = parse_response(raw_response, TranslationResponse, "json")
                fixed_texts = parsed.translations if parsed else []
                
                # Fallback purely JSON loading if parse_response failed to match exact length
                if not fixed_texts or len(fixed_texts) != len(active_indices):
                    try:
                        import re
                        json_match = re.search(r'\[.*\]', raw_response, re.DOTALL)
                        if json_match:
                            fixed_texts = json.loads(json_match.group(0))
                    except:
                        pass
                
                if len(fixed_texts) != len(active_indices):
                    self.logger.error(f"Length mismatch: Expected {len(active_indices)}, got {len(fixed_texts)}")
                    continue
                    
                # 3. Apply fixes and validate
                for idx_in_batch, fixed_text in enumerate(fixed_texts):
                    orig_idx = active_indices[idx_in_batch]
                    state = current_state[orig_idx]
                    
                    state["suggested_fix"] = fixed_text
                    
                    results = validator.validate_entry(
                        game_id=game_id,
                        key=state["key"],
                        value=fixed_text,
                        source_value=state["source"]
                    )
                    
                    errors = [r for r in results if r.level.value == "error"]
                    if not errors:
                        state["is_fixed"] = True
                        state["error_messages"] = []
                        state["error_details"] = []
                    else:
                        state["error_messages"] = [e.message for e in errors]
                        state["error_details"] = [e.details for e in errors if e.details]
                        state["target"] = fixed_text # Update target to the current failed attempt for the next prompt
            except Exception as e:
                self.logger.error(f"Batch Fix API Call failed: {e}")
                
        # Return summary
        results_list = []
        for state in current_state:
            results_list.append({
                "file_name": state["file_name"],
                "key": state["key"],
                "suggested_fix": state["suggested_fix"] if state["suggested_fix"] else state["target"],
                "status": "SUCCESS" if state["is_fixed"] else "FAILED",
                "parity_message": "Validation passed." if state["is_fixed"] else " | ".join(state["error_messages"])
            })
            
        return {"results": results_list}

    def _build_batch_prompt(self, active_issues: List[Dict[str, Any]], game_id: str) -> str:
        """
        Builds the PROMPT for the batch fix, injecting dynamic Few-Shot examples based on the specific errors present in the batch.
        """
        import json
        from scripts.config.validators.fixer_examples import get_examples_for_game
        
        # 1. Identify error categories present in this batch
        error_types_present = set()
        for issue in active_issues:
            combined_error_text = " ".join(issue["error_messages"] + issue["error_details"]).lower()
            if "parity" in combined_error_text or "数量不一致" in combined_error_text or "missing" in combined_error_text or "丢" in combined_error_text or "$" in combined_error_text:
                error_types_present.add("VARIABLE_PARITY")
            if "tag" in combined_error_text or "标签" in combined_error_text or "§" in combined_error_text or "不成对" in combined_error_text or "#" in combined_error_text:
                error_types_present.add("FORMATTING_TAG")
            if "banned" in combined_error_text or "未知" in combined_error_text or "invalid" in combined_error_text:
                error_types_present.add("BANNED_CHARS")
                
        # 2. Build dynamic few-shot examples via the new configuration mapping
        examples = get_examples_for_game(game_id, error_types_present)
            
        examples_text = ""
        if examples:
            examples_text = "--- 常见错误修正范例 (Few-Shot Examples) ---\n" + "\n".join(examples) + "\n----------------------------------------"

        # 3. Assemble the payload
        payload_items = []
        for i, issue in enumerate(active_issues):
            errors = " | ".join(issue["error_messages"] + issue["error_details"])
            payload_items.append(
                f"Item {i+1}:\n"
                f"  Source: {issue['source']}\n"
                f"  Bad Translation: {issue['target']}\n"
                f"  Reported Error: {errors}"
            )
            
        prompt = (
            "### SYSTEM ROLE\n"
            "You are an elite Game Localization Engine (QA-Validator mode). Your sole mission is to REPAIR technical formatting errors in translations. "
            "You must ensure that all technical tags, variables, and symbols in the 'Source' are perfectly mirrored or correctly handled in the 'Fixed Translation'.\n\n"
            f"{examples_text}\n\n"
            "### REPAIR GUIDELINES (GOLDEN RULES)\n"
            "1. **ZERO TOLERANCE**: Do NOT translate or localize any variables inside $...$, [Concept...], [SCOPE...], or icons like @...! or £...£. Keep them exactly as they appear in the Source.\n"
            "2. **TAG CLOSURE**: Ensure all color tags (e.g., §Y or #P) are correctly closed (e.g., §! or #!) as per the game's specific rule.\n"
            "3. **OUTPUT FORMAT**: You must output a JSON array of strings. Return ONLY the JSON. No conversational filler, no markdown code blocks (unless the environment requires it), just the raw JSON array.\n"
            f"4. **ITEM COUNT**: I will provide {len(active_issues)} items. You MUST provide exactly {len(active_issues)} repaired strings in the array.\n\n"
            "### ITEMS TO REPAIR\n" +
            "\n\n".join(payload_items) + "\n\n"
            "### JSON OUTPUT PREVIEW\n"
            "[\n  \"Repaired String 1\",\n  \"Repaired String 2\"\n]"
        )
        return prompt

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
