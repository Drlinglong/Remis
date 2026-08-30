# scripts/core/deepseek_handler.py
import os
from openai import OpenAI
import logging

from scripts.core.base_handler import BaseApiHandler

class DeepSeekHandler(BaseApiHandler):
    """DeepSeek API Handler子类"""

    def initialize_client(self):
        """【必须由子类实现】初始化并返回DeepSeek的API客户端 (使用OpenAI兼容模式)。"""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            self.logger.error("API Key 'DEEPSEEK_API_KEY' not found in environment variables.")
            raise ValueError("DEEPSEEK_API_KEY not set")

        try:
            provider_config = self.get_provider_config()
            base_url = provider_config.get("base_url", "https://api.deepseek.com")
            
            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            
            model_name = provider_config.get("default_model", "deepseek-v4-flash")
            self.logger.info(f"DeepSeek client initialized successfully, using model: {model_name}")
            self.logger.info(f"Using base URL: {base_url}")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing DeepSeek client: {e}")
            raise

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        """【必须由子类实现】执行对DeepSeek API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "deepseek-v4-flash")
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
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.exception(f"DeepSeek API call failed: {e}")
            raise

    def _apply_reasoning_to_openai_kwargs(self, kwargs: dict) -> dict:
        """Route DeepSeek effort at top level and thinking through extra_body."""
        parameters = self._reasoning_request_parameters()
        if not parameters:
            return kwargs

        extra_parameters = dict(parameters)
        reasoning_effort = extra_parameters.pop("reasoning_effort", None)
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort
        if extra_parameters:
            existing_extra_body = kwargs.get("extra_body") or {}
            kwargs["extra_body"] = {**existing_extra_body, **extra_parameters}
        return kwargs
