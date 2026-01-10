# scripts/core/base_handler.py
import time
import logging
from abc import ABC, abstractmethod

from scripts.utils import i18n
from scripts.app_settings import MAX_RETRIES, FALLBACK_FORMAT_PROMPT, APP_DATA_DIR
from scripts.core.parallel_processor import BatchTask
from scripts.utils.punctuation_handler import generate_punctuation_prompt
from scripts.core.glossary_manager import glossary_manager
from scripts.utils.structured_parser import parse_response
from scripts.utils.text_clean import mask_special_tokens
from scripts.core.prompt_manager import prompt_manager


class BaseApiHandler(ABC):
    """【基类】API Handler 抽象基类，封装通用逻辑。"""

    def __init__(self, provider_name: str, model_id: str = None):
        """
        通用的构造函数。
        """
        self.provider_name = provider_name
        self.model_id = model_id
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client = self.initialize_client()

    def get_provider_config(self) -> dict:
        """
        获取提供商的配置，合并默认配置和用户覆盖配置。
        """
        from scripts.app_settings import API_PROVIDERS
        from scripts.app_settings import config_manager
        
        base_config = API_PROVIDERS.get(self.provider_name, {}).copy()
        user_overrides = config_manager.get_value("provider_config", {}).get(self.provider_name, {})
        
        # Merge user overrides
        if user_overrides:
            # Priority: 1. Request param (self.model_id), 2. User Override, 3. Base Default
            selected_model = self.model_id or user_overrides.get("selected_model")
            available_models = base_config.get("available_models", [])
            
            # Use selected model only if it exists in the available list or is a custom model
            if selected_model:
                # If available_models is defined and not empty, enforce strict validation
                if available_models:
                    if selected_model in available_models:
                        base_config["default_model"] = selected_model
                    else:
                        self.logger.warning(f"Selected model '{selected_model}' for provider '{self.provider_name}' is not in available list. Falling back to default: {base_config.get('default_model')}")
                else:
                    # If available_models is empty (e.g. Local LLMs), accept any model name
                    base_config["default_model"] = selected_model

            if "api_url" in user_overrides and user_overrides["api_url"]:
                base_config["base_url"] = user_overrides["api_url"]
        elif self.model_id:
            # If no overrides but we have a request model, use it
            base_config["default_model"] = self.model_id
            
        return base_config

    @abstractmethod
    def initialize_client(self):
        """【必须由子类实现】初始化并返回特定于该Provider的API客户端。"""
        pass

    @abstractmethod
    def _call_api(self, client: any, prompt: str) -> str:
        """【必须由子类实现】执行对特定API的调用并返回原始文本响应。"""
        pass

    def _build_prompt(self, task: BatchTask) -> str:
        """
        【通用逻辑】根据任务构建完整的翻译提示。
        """
        chunk = task.texts
        source_lang = task.file_task.source_lang
        target_lang = task.file_task.target_lang
        game_profile = task.file_task.game_profile
        mod_context = task.file_task.mod_context
        batch_num = task.batch_index + 1



        # Apply Token Masking (Newlines & Quotes)
        masked_chunk = [mask_special_tokens(txt) for txt in chunk]
        numbered_list = "\n".join(f'{j + 1}. "{txt}"' for j, txt in enumerate(masked_chunk))

        effective_target_lang_name = target_lang.get("custom_name", target_lang["name"]) if target_lang.get("is_shell") else target_lang["name"]

        effective_target_lang_name = target_lang.get("custom_name", target_lang["name"]) if target_lang.get("is_shell") else target_lang["name"]

        # Use PromptManager to get the effective prompt (handling overrides)
        prompt_template = prompt_manager.get_effective_prompt(game_profile["id"])
        if not prompt_template:
            # Fallback if for some reason it's missing (shouldn't happen if game_profile is valid)
            prompt_template = game_profile.get("prompt_template", "")

        base_prompt = prompt_template.format(
            source_lang_name=source_lang["name"],
            target_lang_name=effective_target_lang_name,
        )
        context_prompt_part = (
            f"CRITICAL CONTEXT: The mod you are translating is '{mod_context}'. "
            "Use this information to ensure all translations are thematically appropriate.\n"
        )

        glossary_prompt_part = ""
        # [DEBUG] Check glossary state before extraction
        loaded_glossary = glossary_manager.get_glossary_for_translation()
        if loaded_glossary:
            entry_count = len(loaded_glossary.get('entries', []))
            self.logger.info(f"[DEBUG-HANDLER] Glossary loaded with {entry_count} entries. Attempting extraction...")
            if entry_count == 0:
                self.logger.warning(f"[DEBUG-HANDLER] Glossary object exists but has 0 entries!")
        else:
            self.logger.info(f"[DEBUG-HANDLER] No glossary loaded (get_glossary_for_translation returned None).")

        if loaded_glossary:
            relevant_terms = glossary_manager.extract_relevant_terms(
                chunk, source_lang["code"], target_lang["code"]
            )
            if relevant_terms:
                glossary_prompt_part = glossary_manager.create_dynamic_glossary_prompt(
                    relevant_terms, source_lang["code"], target_lang["code"]
                ) + "\n\n"
                self.logger.info(i18n.t("batch_translation_glossary_injected", batch_num=batch_num, count=len(relevant_terms)))

        punctuation_prompt = generate_punctuation_prompt(
            source_lang["code"],
            target_lang["code"]
        )

        effective_format_prompt = prompt_manager.get_effective_format_prompt(game_profile["id"])
        
        if effective_format_prompt:
             format_prompt_part = effective_format_prompt.format(
                chunk_size=len(chunk),
                numbered_list=numbered_list
            )
        else:
            format_prompt_part = FALLBACK_FORMAT_PROMPT.format(
                chunk_size=len(chunk),
                numbered_list=numbered_list
            )

        punctuation_prompt_part = f"\nPUNCTUATION CONVERSION:\n{punctuation_prompt}\n" if punctuation_prompt else ""
        
        # Add a "Final Warning" section for Victoria 3 specifically
        final_warning = ""
        if game_profile["id"] == "victoria3":
            final_warning = (
                "\n🚨 FINAL MANDATORY REMINDER FOR VICTORIA 3:\n"
                "- DO NOT translate the label inside [Concept('key', 'Label')]. Keep it English.\n"
                "- DO NOT translate anything inside [SCOPE...].\n"
                "- Ensure the JSON format is strictly followed.\n"
            )

        prompt = base_prompt + context_prompt_part + glossary_prompt_part + format_prompt_part + punctuation_prompt_part + final_warning
        return prompt

    def _parse_response(self, response: str, original_texts: list[str], target_lang_code: str) -> list[str] | None:
        """
        【通用逻辑】调用结构化解析器来解析API响应。
        -   成功：返回翻译文本列表。
        -   失败：返回None，以触发上游的重试机制。
        """

        parsed_model = parse_response(response, target_lang=target_lang_code)
        if parsed_model:
            return parsed_model.translations
        return None

    def translate_batch(self, task: BatchTask) -> BatchTask:
        """
        【核心工作流】处理单个批次的翻译任务，包含重试逻辑。
        """
        prompt = self._build_prompt(task)
        batch_num = task.batch_index + 1
        start_time = time.time() # <--- 添加时间记录

        for attempt in range(MAX_RETRIES):
            try:
                # Apply global rate limiting
                from scripts.utils.rate_limiter import rate_limiter
                rate_limiter.wait()

                raw_response = self._call_api(self.client, prompt)
                translated_texts = self._parse_response(raw_response, task.texts, task.file_task.target_lang["code"])

                # Check for success: must not be None, must not be the original list, and length must match.
                if translated_texts is not None and translated_texts is not task.texts and len(translated_texts) == len(task.texts):
                    task.translated_texts = translated_texts
                    elapsed_time = time.time() - start_time # <--- 计算耗时
                    self.logger.info(i18n.t("batch_success", batch_num=batch_num, attempt=attempt + 1, elapsed_time=elapsed_time)) # <--- 传递参数
                    return task
                else:
                    self.logger.warning(
                        f"Response parsing failed for batch {batch_num} on attempt {attempt + 1}. "
                        f"Expected {len(task.texts)} items, got {len(translated_texts) if translated_texts else 0}."
                    )
                    raise ValueError("Response parsing failed, triggering retry.")

            except Exception as e:
                self.logger.exception(f"API call failed for batch {batch_num} on attempt {attempt + 1}: {e}")

            if attempt < MAX_RETRIES - 1:
                delay = (attempt + 1) * 2
                self.logger.warning(i18n.t("retrying_batch", batch_num=batch_num, attempt=attempt + 1, max_retries=MAX_RETRIES, delay=delay))
                time.sleep(delay)

        self.logger.error(f"Batch {batch_num} failed after {MAX_RETRIES} attempts. Falling back to original texts.")
        task.failed = True
        task.translated_texts = task.texts
        # We still return the task object so the aggregator can see it failed but has text
        return task

    def _build_single_text_prompt(self, text: str, task_description: str, mod_name: str, source_lang: dict, target_lang: dict, mod_context: str, game_profile: dict) -> str:
        """【通用逻辑】为单条文本构建专用的翻译提示。"""
        base_prompt = game_profile["single_prompt_template"].format(
            mod_name=mod_name,
            task_description=task_description,
            source_lang_name=source_lang["name"],
            target_lang_name=target_lang["name"],
        )

        glossary_prompt_part = ""
        if glossary_manager.get_glossary_for_translation():
            relevant_terms = glossary_manager.extract_relevant_terms(
                [text], source_lang["code"], target_lang["code"]
            )
            if relevant_terms:
                glossary_prompt_part = glossary_manager.create_dynamic_glossary_prompt(
                    relevant_terms, source_lang["code"], target_lang["code"]
                ) + "\n\n"

        punctuation_prompt = generate_punctuation_prompt(
            source_lang["code"],
            target_lang["code"]
        )

        # Apply masking to the single text as well
        masked_text = mask_special_tokens(text)

        prompt = (
            base_prompt
            + f"CRITICAL CONTEXT: The mod's theme is '{mod_context}'. Use this to ensure accuracy.\n"
            + glossary_prompt_part
            + "CRITICAL FORMATTING: Your response MUST ONLY contain the translated text. "
            "DO NOT include explanations, pinyin, or any other text.\n"
            'For example, if the input is "Flavor Pack", your output must be "风味包" and nothing else.\n\n'
            + (f"PUNCTUATION CONVERSION:\n{punctuation_prompt}\n\n" if punctuation_prompt else "")
            + f'Translate this: "{masked_text}"'
        )
        return prompt

    def translate_single_text(self, text: str, task_description: str, mod_name: str, source_lang: dict, target_lang: dict, mod_context: str, game_profile: dict) -> str:
        """【通用工作流】翻译单条文本，带一次调用，失败则返回原文。"""
        if not text:
            return ""

        prompt = self._build_single_text_prompt(text, task_description, mod_name, source_lang, target_lang, mod_context, game_profile)

        try:
            raw_response = self._call_api(self.client, prompt)
            # Simple cleanup for single text
            translated_text = raw_response.strip().strip('"')
            
            # Restore tokens
            from scripts.utils.text_clean import restore_special_tokens
            translated_text = restore_special_tokens(translated_text, target_lang["code"])
            
            return translated_text
        except Exception as e:
            self.logger.exception(f"Single text translation failed for '{text[:30]}...': {e}")
            return text # Fallback to original text

    def generate_with_messages(self, messages: list[dict], temperature: float = 0.7) -> str:
        """
        【通用逻辑】支持基于消息的对话生成。
        默认实现将消息拼接为单个 Prompt，调用 _call_api。
        子类（如 OpenAIHandler）可以覆盖此方法以使用原生 Chat 接口。
        """
        system_instruction = ""
        user_content = ""
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                system_instruction = content
            elif role == 'user':
                user_content += content + "\n"
        
        full_prompt = user_content
        if system_instruction:
            full_prompt = f"{system_instruction}\n\n{user_content}"
            
        try:
            # 使用 _call_api，这意味着所有实现了 _call_api 的子类都自动支持此功能
            return self._call_api(self.client, full_prompt)
        except Exception as e:
            self.logger.exception(f"Generate with messages failed: {e}")
            return ""

