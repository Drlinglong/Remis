# scripts/core/grok_handler.py
import os
from openai import OpenAI
import logging

from scripts.app_settings import API_PROVIDERS
from scripts.core.base_handler import BaseApiHandler

class GrokHandler(BaseApiHandler):
    """Grok API Handler子类"""

    def initialize_client(self):
        """【必须由子类实现】初始化并返回Grok的API客户端 (使用OpenAI兼容模式)。"""
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            self.logger.error("API Key 'XAI_API_KEY' not found in environment variables.")
            raise ValueError("XAI_API_KEY not set")

        try:
            provider_config = self.get_provider_config()
            base_url = provider_config.get("base_url")
            
            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            
            model_name = provider_config.get("default_model", "grok-4-fast-reasoning")
            self.logger.info(f"Grok client initialized successfully, using model: {model_name}")
            self.logger.info(f"Using base URL: {base_url}")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing Grok client: {e}")
            raise

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        """【必须由子类实现】执行对Grok API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "grok-4-fast-reasoning")

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a professional translator for game mods."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.exception(f"Grok API call failed: {e}")
            raise
