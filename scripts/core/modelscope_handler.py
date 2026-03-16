# scripts/core/modelscope_handler.py
import os
from openai import OpenAI
import logging

from scripts.app_settings import API_PROVIDERS
from scripts.core.base_handler import BaseApiHandler

class ModelScopeHandler(BaseApiHandler):
    """ModelScope API Handler子类"""

    def initialize_client(self):
        """【必须由子类实现】初始化并返回ModelScope的API客户端 (使用OpenAI兼容模式)。"""
        api_key = os.getenv("MODELSCOPE_API_KEY")
        if not api_key:
            self.logger.error("API Key 'MODELSCOPE_API_KEY' not found in environment variables.")
            raise ValueError("MODELSCOPE_API_KEY not set")

        try:
            provider_config = self.get_provider_config()
            base_url = provider_config.get("base_url")
            
            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            
            model_name = provider_config.get("default_model")
            self.logger.info(f"ModelScope client initialized successfully, using model: {model_name}")
            self.logger.info(f"Using base URL: {base_url}")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing ModelScope client: {e}")
            raise

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        """【必须由子类实现】执行对ModelScope API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model")

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
            self.logger.exception(f"ModelScope API call failed: {e}")
            raise
