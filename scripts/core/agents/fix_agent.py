import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from scripts.core.base_handler import BaseApiHandler
from scripts.utils.game_format_contract import compare_format_structure

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
        
        # 3. Exact structure check (counts alone are not sufficient).
        parity_passed, parity_msg = self._check_parity(source, suggested_fix, game_id)
        
        status = "SUCCESS" if parity_passed else "WARNING"
        
        return {
            "suggested_fix": suggested_fix,
            "reflection": reflection,
            "status": status,
            "parity_message": parity_msg
        }

    async def fix_issue_loop(
        self,
        source: str,
        target: str,
        error_type: str,
        details: str,
        game_id: str,
        max_retries: int = 3,
        target_lang_code: Optional[str] = None,
        dynamic_valid_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
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

        if self._source_format_needs_review(
            validator,
            source,
            target,
            game_id,
            target_lang_code,
            dynamic_valid_tags,
        ):
            return {
                "suggested_fix": target,
                "reflection": "The source format is unbalanced; no target repair was attempted.",
                "status": "REVIEW",
                "disposition": "source_issue",
                "parity_message": "Source format requires source-side review.",
            }
        
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
                source_value=source,
                target_lang=target_lang_code,
                dynamic_valid_tags=dynamic_valid_tags,
            )
            
            source_issues = [
                result for result in results
                if (getattr(result, "details_params", None) or {}).get("classification") == "source_defect"
            ]
            if source_issues:
                return {
                    "suggested_fix": target,
                    "reflection": "The source format is unbalanced; no target repair was attempted.",
                    "status": "REVIEW",
                    "disposition": "source_issue",
                    "parity_message": "Source format requires source-side review.",
                }

            blocking = self._blocking_validation_results(results)
            variations = [
                result for result in results
                if (getattr(result, "details_params", None) or {}).get("classification") == "possible_reasonable_variation"
            ]
            if not blocking and variations:
                assessment = await self._assess_possible_variation(
                    source,
                    suggested_fix,
                    variations,
                )
                if assessment["verdict"] == "damage":
                    current_error_type = " | ".join([e.message for e in variations])
                    current_details = " | ".join([e.details for e in variations if e.details])
                    current_target = suggested_fix
                    continue
                return {
                    "suggested_fix": suggested_fix,
                    "reflection": assessment["statement"],
                    "status": "REVIEW",
                    "disposition": (
                        "accepted_reasonable"
                        if assessment["verdict"] == "reasonable"
                        else "human_review"
                    ),
                    "assessment": assessment,
                    "parity_message": assessment["statement"],
                }
            if not blocking:
                self.logger.info("Validator passed. Fix successful.")
                return {
                    "suggested_fix": suggested_fix,
                    "reflection": reflection,
                    "status": "SUCCESS",
                    "parity_message": "Validation passed according to game rules."
                }
            
            # Prepare next iteration
            self.logger.warning(f"Validator failed on attempt {attempt + 1}. Updating prompts.")
            current_error_type = " | ".join([e.message for e in blocking])
            current_details = " | ".join([e.details for e in blocking if e.details])
            current_target = suggested_fix
            
        return {
            "suggested_fix": suggested_fix,
            "reflection": reflection,
            "status": "FAILED",
            "parity_message": f"Failed after {max_retries} attempts. Remaining errors: {current_error_type}."
        }

    async def fix_batch_loop(
        self,
        issues: List[Dict[str, Any]],
        game_id: str,
        max_retries: int = 3,
        target_lang_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs the Reflexion workflow for a FULL BATCH of issues to save time and tokens.
        """
        from scripts.utils.post_process_validator import PostProcessValidator
        from scripts.utils.structured_parser import parse_response
        from scripts.core.schemas import TranslationResponse
        
        validator = PostProcessValidator()
        
        current_state = self._build_batch_states(issues, target_lang_code)

        resolved_target_lang = self._resolve_batch_target_lang(current_state, target_lang_code)
        attempt_summaries = []
            
        for attempt in range(max_retries):
            # 1. Filter out already fixed issues for the prompt
            active_indices = [
                i for i in range(len(current_state))
                if not current_state[i]["terminal"]
            ]
            if not active_indices:
                self.logger.info("All issues in batch fixed successfully!")
                break
                
            self.logger.info(f"Batch Fix Attempt {attempt + 1}/{max_retries} for {len(active_indices)} issues.")
            fixed_before_attempt = sum(1 for state in current_state if state["is_fixed"])
            attempt_summary = {
                "attempt": attempt + 1,
                "max_retries": max_retries,
                "active_count": len(active_indices),
                "used_reflection": attempt > 0,
                "reflections_generated": 0,
                "fixed_count": 0,
                "remaining_count": len(active_indices),
                "status": "started",
                "message": "",
            }
            
            # 1.5 Generate diagnostic reflections for retries (attempt > 0)
            if attempt > 0:
                self.logger.info(f"Generating diagnostic reflections for {len(active_indices)} remaining issues...")
                reflection_tasks = []
                for idx in active_indices:
                    state = current_state[idx]
                    err_msg = " | ".join(state["error_messages"])
                    err_dtl = " | ".join(state["error_details"])
                    reflection_tasks.append(self._reflect(state["source"], state["target"], err_msg, err_dtl))
                
                reflection_results = await asyncio.gather(*reflection_tasks, return_exceptions=True)
                for idx_in_active, reflection in enumerate(reflection_results):
                    orig_idx = active_indices[idx_in_active]
                    if isinstance(reflection, Exception):
                        self.logger.error(f"Reflection failed for index {orig_idx}: {reflection}")
                        current_state[orig_idx]["reflection"] = ""
                    else:
                        current_state[orig_idx]["reflection"] = reflection
                        attempt_summary["reflections_generated"] += 1
            else:
                for idx in active_indices:
                    current_state[idx]["reflection"] = ""

            prompt = self._build_batch_prompt(
                [current_state[i] for i in active_indices],
                game_id,
                target_lang_code=resolved_target_lang,
            )
            
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
                    except Exception:
                        pass
                
                if len(fixed_texts) != len(active_indices):
                    message = f"Length mismatch: Expected {len(active_indices)}, got {len(fixed_texts)}"
                    self.logger.error(message)
                    attempt_summary["status"] = "invalid_response"
                    attempt_summary["message"] = message
                    attempt_summaries.append(attempt_summary)
                    continue
                    
                # 3. Apply fixes and validate
                for idx_in_batch, fixed_text in enumerate(fixed_texts):
                    orig_idx = active_indices[idx_in_batch]
                    state = current_state[orig_idx]
                    await self._process_batch_candidate(
                        state,
                        fixed_text,
                        validator,
                        game_id,
                    )

                fixed_after_attempt = sum(1 for state in current_state if state["is_fixed"])
                remaining_after_attempt = len([state for state in current_state if not state["terminal"]])
                attempt_summary["fixed_count"] = max(0, fixed_after_attempt - fixed_before_attempt)
                attempt_summary["remaining_count"] = remaining_after_attempt
                attempt_summary["status"] = "completed"
                attempt_summaries.append(attempt_summary)
            except Exception as e:
                self.logger.error(f"Batch Fix API Call failed: {e}")
                attempt_summary["status"] = "api_error"
                attempt_summary["message"] = str(e)
                attempt_summaries.append(attempt_summary)
                
        results_list = self._build_batch_results(current_state)
            
        return {
            "results": results_list,
            "attempts": attempt_summaries,
            "max_retries": max_retries,
        }

    @staticmethod
    def _build_batch_states(
        issues: List[Dict[str, Any]],
        target_lang_code: Optional[str],
    ) -> List[Dict[str, Any]]:
        return [{
            "source": issue["source_str"],
            "target": issue["target_str"],
            "error_messages": [issue["error_type"]],
            "error_details": [issue.get("details", "")],
            "is_fixed": False,
            "terminal": False,
            "disposition": "detected",
            "suggested_fix": "",
            "key": issue["key"],
            "file_name": issue["file_name"],
            "reflection": "",
            "target_lang": issue.get("target_lang") or target_lang_code,
            "dynamic_valid_tags": issue.get("dynamic_valid_tags"),
            "issue_id": issue.get("issue_id"),
            "classification": issue.get("classification"),
        } for issue in issues]

    @staticmethod
    def _build_batch_results(states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{
            "issue_id": state.get("issue_id"),
            "file_name": state["file_name"],
            "key": state["key"],
            "suggested_fix": state["suggested_fix"] or state["target"],
            "status": (
                "SUCCESS" if state["is_fixed"]
                else "REVIEW" if state["terminal"] and state["disposition"] != "detected"
                else "FAILED"
            ),
            "disposition": state["disposition"],
            "classification": state.get("classification"),
            "assessment": state.get("assessment"),
            "parity_message": "Validation passed." if state["is_fixed"] else " | ".join(state["error_messages"]),
        } for state in states]

    async def _process_batch_candidate(
        self,
        state: Dict[str, Any],
        fixed_text: str,
        validator: Any,
        game_id: str,
    ) -> None:
        state["suggested_fix"] = fixed_text
        results = validator.validate_entry(
            game_id=game_id,
            key=state["key"],
            value=fixed_text,
            source_value=state["source"],
            target_lang=state.get("target_lang"),
            dynamic_valid_tags=state.get("dynamic_valid_tags"),
        )
        source_issues = [
            result for result in results
            if (getattr(result, "details_params", None) or {}).get("classification") == "source_defect"
        ]
        blocking = self._blocking_validation_results(results)
        variations = [
            result for result in results
            if (getattr(result, "details_params", None) or {}).get("classification") == "possible_reasonable_variation"
        ]
        if source_issues:
            state["terminal"] = True
            state["disposition"] = "source_issue"
            state["error_messages"] = [result.message for result in source_issues]
            state["error_details"] = [result.details for result in source_issues if result.details]
        elif not blocking and variations:
            assessment = await self._assess_possible_variation(state["source"], fixed_text, variations)
            state["assessment"] = assessment
            if assessment["verdict"] == "damage":
                state["error_messages"] = [result.message for result in variations]
                state["error_details"] = [result.details for result in variations if result.details]
                state["target"] = fixed_text
            else:
                state["terminal"] = True
                state["disposition"] = (
                    "accepted_reasonable"
                    if assessment["verdict"] == "reasonable"
                    else "human_review"
                )
                state["error_messages"] = [assessment["statement"]]
                state["error_details"] = [result.details for result in variations if result.details]
        elif not blocking:
            state["is_fixed"] = True
            state["terminal"] = True
            state["disposition"] = "fixed"
            state["error_messages"] = []
            state["error_details"] = []
        else:
            state["error_messages"] = [error.message for error in blocking]
            state["error_details"] = [error.details for error in blocking if error.details]
            state["target"] = fixed_text

    def _build_batch_prompt(
        self,
        active_issues: List[Dict[str, Any]],
        game_id: str,
        target_lang_code: Optional[str] = None,
    ) -> str:
        """
        Builds the PROMPT for the batch fix, injecting dynamic Few-Shot examples based on the specific errors present in the batch.
        """
        from scripts.config.validators.fixer_examples import (
            get_examples_for_game,
            get_repair_rules_for_game,
            get_structure_examples_for_game,
        )

        target_lang_code = self._resolve_batch_target_lang(active_issues, target_lang_code)
        english_punctuation_rule = ""
        if self._is_english_target(target_lang_code):
            english_punctuation_rule = (
                "12. **PUNCTUATION TRANSLATION**: When localizing to English (en), you MUST translate all Chinese double-byte punctuations "
                "(like '。', '，', '：', '；', '（', '）', '、') to English standard punctuations "
                "('.', ',', ':', ';', '(', ')', ','). Never leave Chinese punctuations in the final target.\n"
            )
        
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

        structure_examples = get_structure_examples_for_game(
            game_id,
            [issue.get("source", "") for issue in active_issues],
        )
        if structure_examples:
            examples_text += (
                ("\n" if examples_text else "")
                + "--- 结构契约示例 (Observed Format Contract) ---\n"
                + "\n".join(structure_examples)
                + "\n----------------------------------------"
            )

        game_rules = get_repair_rules_for_game(game_id)
        game_rules_text = ""
        if game_rules:
            game_rules_text = "### GAME-SPECIFIC RULES\n" + "\n".join(game_rules)

        # 3. Assemble the payload
        payload_items = []
        for i, issue in enumerate(active_issues):
            errors = " | ".join(issue["error_messages"] + issue["error_details"])
            source_text = issue["source"] if issue["source"] else "[SOURCE CONTEXT UNAVAILABLE]"
            
            payload_item = (
                f"Item {i+1}:\n"
                f"  Source: {source_text}\n"
                f"  Bad Translation: {issue['target']}\n"
                f"  Reported Error: {errors}"
            )
            # Inject reflection if available
            if issue.get("reflection"):
                payload_item += f"\n  Diagnostic Reflection: {issue['reflection']}"
                
            payload_items.append(payload_item)
            
        prompt = (
            "### SYSTEM ROLE\n"
            "You are an elite Game Localization Recovery Agent. Your mission is to repair localization output that may contain formatting damage, failed-chunk corruption, or low-quality translation mistakes. "
            "You must preserve technical correctness first, then recover missing or damaged content, and only perform limited source-aware translation revision when the source context is available.\n\n"
            "### TARGET LANGUAGE\n"
            f"{target_lang_code or 'unknown'}\n\n"
            f"{examples_text}\n\n"
            "### REPAIR GUIDELINES (GOLDEN RULES)\n"
            "1. **ZERO TOLERANCE**: Preserve code identifiers and non-translatable parameters inside $...$, [SCOPE...], function or command syntax, and icons like @...! or £...£. Keep those protected tokens exactly as they appear in the Source.\n"
            "2. **TAG CLOSURE**: Ensure all color tags (e.g., §Y or #P) are correctly closed (e.g., §! or #!) as per the game's specific rule.\n"
            "3. **EXACT FORMAT IDENTITY**: Preserve each Source formatting opener character-for-character, including case, marker family, parameters, order, boundaries, and nesting. `#italic` is not interchangeable with `#b`; `#blue` must not become `#b lue`; `§Y` is not interchangeable with `§R`.\n"
            "4. **NO OPAQUE MASKING**: The complete Source and Bad Translation are visible. Never invent aliases such as '变量1' or '[TOKEN_1]' and never hide, replace, or hardcode semantic runtime tokens.\n"
            "5. **THREE REPAIR MODES**: Your repair task may include: (a) format repair, (b) failed-chunk recovery, and (c) limited source-aware revision of obviously bad translations. Always prioritize them in that order.\n"
            "6. **FAILED-CHUNK RECOVERY**: If the translation looks truncated, mechanically damaged, fallback-like, or structurally broken, you may reconstruct the missing content conservatively from the Source.\n"
            "7. **LIMITED REVISION ONLY**: If the Source is available, you may correct clear mistranslations, polarity mistakes, intensity mistakes, omissions, or obviously awkward machine wording. Do NOT freely rewrite for style.\n"
            "8. **SOURCE ANOMALIES**: If the Source itself is unbalanced, do not force the Target to close it or add markers that are absent from the Source.\n"
            "9. **COUNT IS NOT A VERDICT**: Do not add, remove, or substitute formatting merely to equalize counts. A language may merge or omit a repeated expression; such cases require semantic review after your candidate is structurally checked.\n"
            "10. **MISSING SOURCE CONTEXT**: If the Source is marked as unavailable, do best-effort format repair and conservative recovery from the broken translation only. Do not invent semantic details or perform aggressive rewriting.\n"
            "11. **MINIMAL NECESSARY CHANGE**: Keep valid parts of the translation intact. Do not rewrite more than needed to make it technically valid and semantically reasonable.\n"
            "12. **OUTPUT FORMAT**: You must output a JSON array of strings. Return ONLY the JSON. No conversational filler, no markdown code blocks.\n"
            f"13. **ITEM COUNT**: I will provide {len(active_issues)} items. You MUST provide exactly {len(active_issues)} repaired strings in the array.\n"
            "14. **DIAGNOSTIC REFLECTION**: Some items in this batch may contain a 'Diagnostic Reflection' providing deep analysis of why the previous repair attempt failed. You MUST treat this reflection as highly authoritative guidance to correct the specific tag mismatch or semantic error.\n"
            f"{english_punctuation_rule}\n"
            f"{game_rules_text}\n\n"
            "### ITEMS TO REPAIR\n" +
            "\n\n".join(payload_items) + "\n\n"
            "### JSON OUTPUT PREVIEW\n"
            "[\n  \"Repaired String 1\",\n  \"Repaired String 2\"\n]"
        )
        return prompt

    async def _assess_possible_variation(
        self,
        source: str,
        target: str,
        results: List[Any],
    ) -> Dict[str, Any]:
        """Ask for semantic judgment only after deterministic structure checks."""
        diagnostics = [
            {
                "message": result.message,
                "details": result.details,
                "structure": result.details_params or {},
            }
            for result in results
        ]
        prompt = (
            "判断下面的本地化目标文本是否只是语言导致的格式数量变化，还是确实损坏了格式。\n\n"
            f"Source:\n{source}\n\nTarget:\n{target}\n\n"
            f"Deterministic diagnostics:\n{json.dumps(diagnostics, ensure_ascii=False, indent=2)}\n\n"
            "完整保留 Source 和 Target 中的技术 token；不要发明变量别名或替换 token。"
            "如果目标只是合并/省略了重复的可见表达、且所有 token 身份、边界和嵌套仍正确，"
            "verdict 用 reasonable；如果目标删除、改写或错绑了技术结构，使用 damage；"
            "无法确定则使用 uncertain。只返回 JSON："
            '{"verdict":"reasonable|damage|uncertain","statement":"...",'
            '"evidence":["..."],"confidence":0.0}'
        )
        try:
            raw = await self.handler.generate_response(prompt)
            match = re.search(r"\{.*\}", raw or "", re.DOTALL)
            parsed = json.loads(match.group(0)) if match else {}
        except Exception as exc:
            self.logger.warning("Semantic variation assessment failed: %s", exc)
            parsed = {}
        verdict = (
            parsed.get("verdict")
            if parsed.get("verdict") in {"reasonable", "damage", "uncertain"}
            else "uncertain"
        )
        statement = parsed.get("statement") if isinstance(parsed.get("statement"), str) else ""
        if verdict == "reasonable":
            statement = "我认为这是合理的改动"
        elif not statement:
            statement = "Possible format-count variation requires human review."
        evidence = parsed.get("evidence") if isinstance(parsed.get("evidence"), list) else []
        return {
            "verdict": verdict,
            "statement": statement,
            "evidence": [str(item) for item in evidence[:5]],
            "confidence": parsed.get("confidence"),
        }

    @staticmethod
    def _source_format_needs_review(
        validator: Any,
        source: str,
        target: str,
        game_id: str,
        target_lang_code: Optional[str],
        dynamic_valid_tags: Optional[List[str]],
    ) -> bool:
        results = validator.validate_entry(
            game_id=game_id,
            key="mock_key",
            value=target,
            source_value=source,
            target_lang=target_lang_code,
            dynamic_valid_tags=dynamic_valid_tags,
        )
        return any(
            (getattr(result, "details_params", None) or {}).get("classification") == "source_defect"
            for result in results
        )

    @staticmethod
    def _resolve_batch_target_lang(
        issues: List[Dict[str, Any]],
        explicit_target_lang: Optional[str] = None,
    ) -> Optional[str]:
        if explicit_target_lang:
            return explicit_target_lang
        for issue in issues:
            target_lang = issue.get("target_lang")
            if target_lang:
                return str(target_lang)
        return None

    @staticmethod
    def _is_english_target(target_lang_code: Optional[str]) -> bool:
        if not target_lang_code:
            return False
        normalized = str(target_lang_code).strip().lower().replace("_", "-")
        return normalized == "en" or normalized.startswith("en-") or normalized == "english"

    async def _reflect(self, source: str, target: str, error_type: str, details: str) -> str:
        source_for_prompt = source or "[SOURCE CONTEXT UNAVAILABLE]"
        prompt = (
            "You are a Localization Recovery Analyst. Analyze the following translation issue.\n\n"
            f"Source Text: {source_for_prompt}\n"
            f"Translated Text (Broken): {target}\n"
            f"Error Type: {error_type}\n"
            f"Details: {details}\n\n"
            "Explain whether the problem is mainly a formatting issue, a failed-chunk/corruption issue, or a low-quality translation issue. "
            "Focus on technical tags ($ $, [ ], #, §), content loss, polarity/intensity mistakes, and obvious mistranslation. "
            "If source context is unavailable, say that semantic judgment is limited and the repair must rely on the broken translation only. "
            "Be concise."
        )
        response = await self.handler.generate_response(prompt)
        return response.strip()

    async def _suggest_fix(self, source: str, target: str, reflection: str, game_id: str) -> str:
        source_for_prompt = source or "[SOURCE CONTEXT UNAVAILABLE]"
        prompt = (
            "Based on your analysis, provide a RECOVERED version of the translation.\n\n"
            f"Source Text: {source_for_prompt}\n"
            f"Broken Text: {target}\n"
            f"Analysis: {reflection}\n\n"
            "Rules:\n"
            "1. Preserve the intended meaning faithfully.\n"
            "2. Ensure all technical tags are valid for the game engine.\n"
            "3. Repair failed-chunk damage or obvious corruption when present.\n"
            "4. If the source text is available, you may correct clear mistranslations and obviously poor machine wording, but keep edits limited and faithful.\n"
            "5. If the source text is unavailable, perform conservative best-effort repair from the broken translation only.\n"
            "6. Return ONLY the corrected string, no extra text."
        )
        response = await self.handler.generate_response(prompt)
        # Basic cleanup: remove quotes if the LLM added them
        result = response.strip()
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        return result

    def _check_parity(self, source: str, target: str, game_id: str = "hoi4") -> Tuple[bool, str]:
        """
        Ensures that technical structure is preserved exactly for the game.
        """
        diff = compare_format_structure(source, target, game_id)
        if diff.source_issue:
            return False, "Source format is unbalanced; target repair requires review."
        if diff.hard_issues:
            return False, f"Exact structure check failed: {', '.join(diff.hard_issues)}"
        if diff.possible_variations:
            return False, "Possible semantic format variation requires review."
        return True, "Exact structure check passed."

    @staticmethod
    def _blocking_validation_results(results: List[Any]) -> List[Any]:
        """Treat structured hard findings as blocking even when legacy rules warn."""
        return [
            result
            for result in results
            if result.level.value == "error"
            or (getattr(result, "details_params", None) or {}).get("blocking") is True
        ]
