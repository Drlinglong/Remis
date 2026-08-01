"""OpenRouter provider adapter built on its OpenAI-compatible chat API."""

from openai import OpenAI

from scripts.app_settings import get_api_key
from scripts.core.openai_handler import OpenAIHandler


class OpenRouterHandler(OpenAIHandler):
    """Use OpenRouter with explicit Remis attribution and isolated credentials."""

    def initialize_client(self):
        provider_config = self.get_provider_config()
        api_key_env = provider_config.get("api_key_env", "OPENROUTER_API_KEY")
        api_key = get_api_key(self.provider_name, api_key_env)
        if not api_key:
            raise ValueError(f"{api_key_env} not set")

        base_url = provider_config.get("base_url", "https://openrouter.ai/api/v1")
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=300.0,
            default_headers={
                "HTTP-Referer": "https://github.com/Drlinglong/Remis",
                "X-OpenRouter-Title": "Remis",
            },
        )
        model_name = provider_config.get("default_model")
        self.logger.info(
            "OpenRouter client initialized successfully, using model: %s",
            model_name,
        )
        return client
