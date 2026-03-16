# scripts/core/qwen_handler.py
import os
from openai import OpenAI
import logging

from scripts.app_settings import API_PROVIDERS
from scripts.core.base_handler import BaseApiHandler

class QwenHandler(BaseApiHandler):
    """Qwen API Handler子类 (通义千问)"""

    def initialize_client(self):
        """【必须由子类实现】初始化并返回Qwen的API客户端 (使用OpenAI兼容模式)。"""
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            self.logger.error("API Key 'DASHSCOPE_API_KEY' not found in environment variables.")
            raise ValueError("DASHSCOPE_API_KEY not set")
        
        try:
            provider_config = self.get_provider_config()
            base_url = provider_config.get("base_url")
            
            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            
            model_name = provider_config.get("default_model", "qwen-plus")
            self.logger.info(f"Qwen client initialized successfully, using model: {model_name}")
            self.logger.info(f"Using base URL: {base_url}")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing Qwen client: {e}")
            raise

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        """【必须由子类实现】执行对Qwen API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "qwen-plus")
        enable_thinking = provider_config.get("enable_thinking", False)

        try:
            # Qwen的思考功能通过API参数控制，而不是修改prompt
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a professional translator for game mods."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                extra_body={"enable_thinking": enable_thinking}
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.exception(f"Qwen API call failed: {e}")
            raise
