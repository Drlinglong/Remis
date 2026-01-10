# scripts/core/yourfavourite_handler.py
import os
import openai
from openai import OpenAI
import logging

from scripts.app_settings import API_PROVIDERS
from scripts.core.base_handler import BaseApiHandler

class YourFavouriteHandler(BaseApiHandler):
    """(高级)通用OAI兼容API Handler子类"""

    def initialize_client(self):
        """【必须由子类实现】初始化并返回一个通用的、兼容OAI的API客户端。"""
        api_key = os.getenv("YOUR_FAVOURITE_API_KEY")
        if not api_key:
            self.logger.error("API Key 'YOUR_FAVOURITE_API_KEY' not found in environment variables.")
            raise ValueError("YOUR_FAVOURITE_API_KEY not set")

        try:
            provider_config = self.get_provider_config()
            base_url = provider_config.get("base_url")
            if not base_url or base_url == "YOUR_BASE_URL_HERE":
                raise ValueError("Base URL for your_favourite_api is not configured correctly.")

            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            
            model_name = provider_config.get("default_model")
            self.logger.info(f"Custom API client initialized successfully, using model: {model_name}")
            self.logger.info(f"Using base URL: {base_url}")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing Custom API client: {e}")
            raise

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        """【必须由子类实现】执行对针对通用OAI兼容API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model")
        if not model_name or model_name == "YOUR_MODEL_NAME_HERE":
            raise ValueError("Model name for your_favourite_api is not configured correctly.")

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a professional translator for game mods."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000
            )
            return response.choices[0].message.content.strip()
        except openai.NotFoundError as e:
            # 捕获 404 错误 (Model Not Found)
            error_msg = str(e)
            hint = f"Custom API Error (404 Not Found): {error_msg}. "
            
            # 这里通常都是自定义/本地服务，所以提示更直接
            hint += f"请检查您的自定义后端配置。模型 '{model_name}' 可能不存在，或者 URL '{client.base_url}' 不正确。"
            
            self.logger.error(hint)
            raise ValueError(hint) from e
        except Exception as e:
            self.logger.exception(f"Custom API call failed: {e}")
            raise
