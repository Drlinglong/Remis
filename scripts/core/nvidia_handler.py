# scripts/core/nvidia_handler.py
import os
from openai import OpenAI
import logging

from scripts.app_settings import API_PROVIDERS
from scripts.core.base_handler import BaseApiHandler

class NvidiaHandler(BaseApiHandler):
    """NVIDIA NIM API Handler子类"""

    def initialize_client(self):
        """【必须由子类实现】初始化并返回NVIDIA NIM的API客户端 (使用OpenAI兼容模式)。"""
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            self.logger.error("API Key 'NVIDIA_API_KEY' not found in environment variables.")
            raise ValueError("NVIDIA_API_KEY not set")

        try:
            provider_config = self.get_provider_config()
            base_url = provider_config.get("base_url")
            
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                max_retries=0, 
                timeout=60.0
            )
            
            model_name = provider_config.get("default_model")
            self.logger.info(f"NVIDIA NIM client initialized successfully, using model: {model_name}")
            self.logger.info(f"Using base URL: {base_url}")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing NVIDIA NIM client: {e}")
            raise

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        """【必须由子类实现】执行对NVIDIA NIM API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model")

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a professional translator for game mods."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000
            )
            
            # Robust extraction of content
            message = response.choices[0].message
            content = getattr(message, "content", None)
            reasoning = getattr(message, "reasoning_content", None)
            
            # Use reasoning content if primary content is empty (common for some NIM thinking models)
            if not content and reasoning:
                self.logger.warning(f"NVIDIA NIM: 'content' is empty, using 'reasoning_content' for model {model_name}")
                content = reasoning
            
            if content is None:
                self.logger.error(f"NVIDIA NIM: Both 'content' and 'reasoning_content' are None for model {model_name}")
                self.logger.debug(f"Full response object: {response}")
                return "ERROR: API returned empty content (NVIDIA NIM)"

            content = content.strip()
            
            # Strip <think>...</think> tags if present
            import re
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            # --- Robust JSON Post-Processing ---
            # If the output looks like it might contain nested lists or be embedded in text
            # some models might return "Here is your JSON: [ ... ]"
            try:
                # 1. Try to find the first '[' and last ']' to extract potential JSON array
                start_idx = content.find('[')
                end_idx = content.rfind(']')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx+1]
                    # 2. Parse and flatten if it's a list of lists
                    import json
                    from json_repair import repair_json
                    repaired = repair_json(json_str)
                    data = json.loads(repaired)
                    if isinstance(data, list):
                        flattened = []
                        for item in data:
                            if isinstance(item, list):
                                # Flatten nested list: [["A"], ["B"]] -> ["A", "B"]
                                # Combine items if multiple in a sub-list, though usually it's just one
                                flattened.append(" ".join(str(i) for i in item))
                            else:
                                flattened.append(str(item))
                        # Update content with repaired and flattened JSON
                        content = json.dumps(flattened, ensure_ascii=False)
            except Exception as je:
                self.logger.warning(f"Failed to auto-flatten/repair NVIDIA response: {je}")

            return content
        except Exception as e:
            self.logger.exception(f"NVIDIA NIM API call failed: {e}")
            raise
