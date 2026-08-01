# scripts/core/openai_handler.py
import openai
from openai import OpenAI

from scripts.app_settings import get_api_key
from scripts.core.base_handler import BaseApiHandler

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
            model_name = provider_config.get("default_model", "gpt-5.6-terra")
            self.logger.info(f"OpenAI client initialized successfully, using model: {model_name}")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing OpenAI client: {e}")
            raise

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        """【必须由子类实现】执行对OpenAI API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "gpt-5.6-terra")
        
        enable_thinking = provider_config.get("enable_thinking", False)
        reasoning_effort_value = provider_config.get("reasoning_effort")

        extra_params = {}
        if not enable_thinking and reasoning_effort_value:
            extra_params["reasoning_effort"] = reasoning_effort_value

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a professional translator for game mods."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=4000,  # 保持较大的token以适应大批次
                **extra_params
            )
            return response.choices[0].message.content.strip()
        except openai.NotFoundError as e:
            # 捕获 404 错误 (Model Not Found) - 特别针对本地 LLM 用户
            error_msg = str(e)
            hint = f"OpenAI API Error (404 Not Found): {error_msg}. "
            
            # 尝试判断是否是本地环境
            base_url = str(client.base_url)
            if "localhost" in base_url or "127.0.0.1" in base_url:
                 hint += f"由于您使用的是本地服务器 ({base_url})，请务必检查模型 '{model_name}' 是否已加载/安装。"
            else:
                 hint += f"请检查模型 '{model_name}' 是否存在且您有权访问。"
            
            self.logger.error(hint)
            raise ValueError(hint) from e
        except Exception as e:
            self.logger.exception(f"OpenAI API call failed: {e}")
            # 重新引发异常，让基类的重试逻辑捕获
            raise

    def generate_with_messages(self, messages: list[dict], temperature: float = 0.7) -> str:
        """
        Supports chat-like interaction for NeologismMiner.
        """
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "gpt-5.6-terra")
        
        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.exception(f"OpenAI chat generation failed: {e}")
            raise
