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
                timeout=300.0
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
        self.last_completion_source = "assistant_content"

        try:
            request_kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a professional translator for game mods."},
                    {"role": "user", "content": prompt}
                ],
            }
            response = client.chat.completions.create(
                **self._apply_reasoning_to_openai_kwargs(request_kwargs)
            )
            self._record_model_response(response)
            
            # Robust extraction of content
            message = response.choices[0].message
            content = getattr(message, "content", None)
            if not isinstance(content, str) or not content.strip():
                raise ValueError(
                    "NVIDIA NIM returned no final assistant content. "
                    "reasoning_content is intentionally ignored; configure the model "
                    "to emit its final translation in message.content."
                )

            # Preserve the adapter-selected final content exactly up to outer
            # whitespace. Parsing and validation must see what the model emitted.
            return content.strip()
        except Exception as e:
            self.logger.exception(f"NVIDIA NIM API call failed: {e}")
            raise
