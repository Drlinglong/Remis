"""OpenRouter provider adapter built on its OpenAI-compatible chat API."""

from openai import OpenAI

from scripts.app_settings import get_api_key
from scripts.core.openai_handler import OpenAIHandler


class OpenRouterHandler(OpenAIHandler):
    """Use OpenRouter with explicit Remis attribution and isolated credentials."""

    def _chat_options(self, temperature: float | None = None) -> dict:
        provider_config = self.get_provider_config()
        options = {
            "model": provider_config.get("default_model"),
            "max_tokens": int(provider_config.get("max_tokens", 32768)),
            "extra_body": {
                "reasoning": {
                    "effort": provider_config.get("reasoning_effort", "high"),
                    "exclude": True,
                }
            },
        }
        model_name = str(options["model"] or "")
        if temperature is not None and not model_name.startswith("openai/gpt-5.6"):
            options["temperature"] = temperature
        return options

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

    def _call_api(self, client: OpenAI, prompt: str) -> str:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional translator for game mods.",
                },
                {"role": "user", "content": prompt},
            ],
            **self._chat_options(),
        )
        return response.choices[0].message.content.strip()

    def generate_with_messages(
        self,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> str:
        response = self.client.chat.completions.create(
            messages=messages,
            **self._chat_options(temperature),
        )
        return response.choices[0].message.content.strip()

    def generate_structured_with_messages(
        self,
        messages: list[dict],
        *,
        schema: dict,
        schema_name: str,
        temperature: float = 0.0,
    ) -> str:
        response = self.client.chat.completions.create(
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": False,
                    "schema": schema,
                },
            },
            **self._chat_options(temperature),
        )
        return response.choices[0].message.content.strip()
