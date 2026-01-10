import logging
from scripts.core.parallel_processor import BatchTask
from scripts.core.openai_handler import OpenAIHandler
from scripts.utils import i18n
# from scripts.utils.text_clean import mask_special_tokens, restore_special_tokens # REMOVED

class HunyuanHandler(OpenAIHandler):
    """
    Hunyuan-MT Handler (via vLLM/OpenAI-compatible API).
    
    Features:
    - Uses Hunyuan-MT specific prompt templates.
    - Forces plain text parsing (no JSON enforcement).
    - post-processing: Normalizes full-width quotes to ASCII quotes for Paradox game compatibility.
    - DIRECT RAW TEXT input: No masking of variables, trusting the LLM to understand context.
    """

    def get_provider_config(self):
        """
        Override processing config to enforce chunk_size=1, 
        ignoring external config to prevent line mismatch errors.
        """
        config = super().get_provider_config()
        config["chunk_size"] = 1
        return config

    def initialize_client(self):
        """
        Initialize OpenAI client pointing to the local vLLM instance.
        """
        from openai import OpenAI
        import os
        
        provider_config = self.get_provider_config()
        base_url = provider_config.get("base_url", "http://localhost:8000/v1")
        # vLLM local usually doesn't need a key, but library insists on one. "EMPTY" is standard.
        api_key = os.getenv("HUNYUAN_API_KEY", "EMPTY") 
        
        self.logger.info(f"Initializing Hunyuan client with Base URL: {base_url}")
        return OpenAI(base_url=base_url, api_key=api_key)

    def _build_prompt(self, task: BatchTask) -> str:
        """
        Builds the prompt using Hunyuan-MT templates.
        Note: Hunyuan-MT works best withsingle segments or small batches joined by newlines.
        """
        chunk = task.texts
        source_lang_code = task.file_task.source_lang["code"]
        target_lang_name = task.file_task.target_lang["name"]
        
        # [MODIFIED] Direct input without masking to preserve variable context (e.g. [Root.GetName])
        # The user explicitly requested to trust the LLM with raw Paradox variables 
        # instead of masking them, to allow context-aware translation.
        source_text = "\n".join(chunk)

        # 2. Select Template
        # Template for ZH<=>XX (Target is ZH or Source is ZH)
        # Optimized with Few-shot examples to reduce verbosity
        if "zh" in task.file_task.target_lang["code"].lower():
            prompt_template = (
                "你是一个游戏汉化专家。请直接给出最简练的中文翻译，不要添加任何括号、解释或备注。\n\n"
                "示例：\n"
                "原文：Convoy Raiding\n"
                "译文：袭击船队\n\n"
                "原文：Market Access\n"
                "译文：市场接入度\n\n"
                "原文：{source_text}\n"
                "译文："
            )
        else:
            # Template for XX<=>XX (excluding ZH)
            # "Translate the following segment into <target_language>, without additional explanation.\n\n<source_text>"
            prompt_template = "Translate the following segment into {target_language}, without additional explanation.\n\n{source_text}"

        prompt = prompt_template.format(
            target_language=target_lang_name,
            source_text=source_text
        )
        
        return prompt

    def _parse_response(self, response: str, original_texts: list[str], target_lang_code: str) -> list[str] | None:
        """
        Overrides the default JSON parser.
        Hunyuan-MT returns plain text. We parse it by splitting lines (if batch > 1) 
        and cleaning quotes.
        """
        # 1. Post-process: No specific quote normalization. 
        # We trust the model's output and do not want to convert smart quotes to ASCII 
        # because that would break the YAML syntax when wrapped in double quotes.
        cleaned_response = response
        
        # 2. Split lines (assuming 1:1 mapping with input newlines)
        if len(original_texts) > 1:
            lines = cleaned_response.strip().split('\n')
            
            # [FIX] Filter out empty lines which might be artifacts of the model's output formatting
            # But only if the count doesn't match. If count matches including empty lines, keep them.
            if len(lines) != len(original_texts):
                 non_empty_lines = [line for line in lines if line.strip()]
                 if len(non_empty_lines) == len(original_texts):
                     lines = non_empty_lines
            
            # Simple alignment check
            if len(lines) != len(original_texts):
                self.logger.warning(
                    f"Hunyuan-MT line mismatch. Input: {len(original_texts)}, Output: {len(lines)}. \n"
                    f"Input: {original_texts}\nOutput: {lines}"
                )
                return None
            
            translated_texts = lines
        else:
            # Single line case (Recommended)
            translated_texts = [cleaned_response.strip()]

        # [MODIFIED] No token restoration needed as we didn't mask.
        return translated_texts

    def _call_api(self, client, prompt: str) -> str:
        """
        Calls the OpenAI-compatible API with Hunyuan recommmended parameters.
        """
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "hunyuan-mt-7b")
        
        # Recommended params from Hunyuan docs:
        # top_k: 20, top_p: 0.6, repetition_penalty: 1.05, temperature: 0.7
        extra_body = {
            "top_k": 20,
            "repetition_penalty": 1.05
        }

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                top_p=0.6,
                max_tokens=2048,
                extra_body=extra_body
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.exception(f"Hunyuan-MT API call failed: {e}")
            raise

    def translate_batch(self, task: BatchTask) -> list[str]:
        """
        Overrides the default batch translation to enforce serial processing.
        This ignores the incoming batch structure and processes each text individually
        to prevent line mismatch errors common with Hunyuan-MT.
        """
        results = []
        original_chunk_size = len(task.texts)
        
        if original_chunk_size > 1:
            self.logger.info(f"Intercepted batch of {original_chunk_size} items. Processing serially for Hunyuan stability...")
        
        for i, text in enumerate(task.texts):
            # Create a mini-task for a single item
            mini_task = BatchTask(
                texts=[text],
                file_task=task.file_task,
                batch_index=task.batch_index + i,
                start_index=task.start_index + i if hasattr(task, 'start_index') else 0, # Best effort or dummy
                end_index=task.start_index + i + 1 if hasattr(task, 'start_index') else 1
            )
            
            try:
                # Reuse the existing single-item pipeline
                prompt = self._build_prompt(mini_task)
                response = self._call_api(self.client, prompt)
                target_lang = task.file_task.target_lang["code"]
                
                # Parse single response
                parsed = self._parse_response(response, [text], target_lang)
                if parsed and len(parsed) == 1:
                    results.append(parsed[0])
                else:
                    # Fallback if parsing fails even for single item
                    self.logger.warning(f"Failed to parse single item response: {response}")
                    results.append(response) # Return raw response as fallback? Or None?
                    # Ideally we should raise or return something indicative. 
                    # But kept simple: append the raw cleaned text.
            except Exception as e:
                self.logger.error(f"Failed to translate item {i}: {text}. Error: {e}")
                results.append(text) # Fallback to original
        
        # [FIX] ParallelProcessor expects a BatchTask object returned, not a list of strings
        task.translated_texts = results
        return task
