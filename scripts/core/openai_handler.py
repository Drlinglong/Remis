# scripts/core/openai_handler.py
from openai import OpenAI

from scripts.app_settings import get_api_key
from scripts.core.base_handler import BaseApiHandler
from scripts.core.provider_errors import raise_safe_provider_fatal_error


_GPT6_MODELS = {"gpt-6-astra", "gpt-6-sol", "gpt-6-luna"}


class OpenAIHandler(BaseApiHandler):
    """OpenAI API Handler子类"""

    def initialize_client(self):
        """
        初始化并返回OpenAI的API客户端。
        """
        provider_config = self.get_provider_config()
        api_key_env = provider_config.get("api_key_env")
        if not api_key_env:
            raise ValueError(
                f"Provider '{self.provider_name}' does not declare an API key environment variable."
            )

        api_key = get_api_key(self.provider_name, api_key_env)
        if not api_key:
            raise ValueError(f"{api_key_env} not set")

        base_url = provider_config.get("base_url")

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=300.0)
            model_name = provider_config.get("default_model", "gpt-5.6-luna")
            self.logger.info(f"OpenAI client initialized successfully, using model: {model_name}")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing OpenAI client: {e}")
            raise

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        """【必须由子类实现】执行对OpenAI API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "gpt-5.6-luna")
        
        try:
            request_kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "You are a professional translator for game mods."},
                    {"role": "user", "content": prompt}
                ],
                "max_completion_tokens": 4000,
            }
            response = client.chat.completions.create(
                **self._apply_reasoning_to_openai_kwargs(request_kwargs)
            )
            self._record_model_response(response)
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise_safe_provider_fatal_error(e, provider=self.provider_name)
            self.logger.exception(f"OpenAI API call failed: {e}")
            # 重新引发异常，让基类的重试逻辑捕获
            raise

    def generate_with_messages(
        self,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> str:
        """
        Supports chat-like interaction for NeologismMiner.
        """
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "gpt-5.6-luna")
        
        try:
            request_kwargs = {
                "model": model_name,
                "messages": messages,
            }
            reasoning_parameters = self._reasoning_request_parameters()
            if (
                model_name not in _GPT6_MODELS
                or reasoning_parameters.get("reasoning_effort") == "none"
            ):
                request_kwargs["temperature"] = temperature
            response = self.client.chat.completions.create(
                **self._apply_reasoning_to_openai_kwargs(request_kwargs)
            )
            self._record_model_response(response)
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise_safe_provider_fatal_error(e, provider=self.provider_name)
            self.logger.exception(f"OpenAI chat generation failed: {e}")
            raise
