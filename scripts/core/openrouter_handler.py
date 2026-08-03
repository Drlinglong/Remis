"""OpenRouter provider adapter built on its OpenAI-compatible chat API."""

import json

from openai import OpenAI

from scripts.app_settings import get_api_key
from scripts.core.openai_handler import OpenAIHandler
from scripts.core.strict_json_schema import strict_json_schema


class OpenRouterHandler(OpenAIHandler):
    """Use OpenRouter with explicit Remis attribution and isolated credentials."""

    STRUCTURED_RESPONSE_ATTEMPTS = 2

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
        options = self._chat_options(temperature)
        extra_body = dict(options.get("extra_body") or {})
        extra_body.update({
            "provider": {"require_parameters": True},
            "plugins": [{"id": "response-healing"}],
        })
        options["extra_body"] = extra_body
        request = {
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": strict_json_schema(schema),
                },
            },
            **options,
        }
        response = self._create_structured_completion(request)
        return response.choices[0].message.content.strip()

    def _create_structured_completion(self, request: dict):
        """Retry once when the provider's outer response envelope is invalid JSON."""

        for attempt in range(1, self.STRUCTURED_RESPONSE_ATTEMPTS + 1):
            try:
                return self.client.chat.completions.create(**request)
            except Exception as exc:
                if not self._is_response_envelope_decode_error(exc):
                    raise
                if attempt >= self.STRUCTURED_RESPONSE_ATTEMPTS:
                    raise
                self.logger.warning(
                    "OpenRouter returned an invalid JSON response envelope; "
                    "retrying structured request once (line=%s, column=%s, position=%s)",
                    getattr(exc, "lineno", "unknown"),
                    getattr(exc, "colno", "unknown"),
                    getattr(exc, "pos", "unknown"),
                )
        raise RuntimeError("Structured response retry loop ended unexpectedly")

    @staticmethod
    def _is_response_envelope_decode_error(exc: Exception) -> bool:
        return isinstance(exc, json.JSONDecodeError) or exc.__class__.__name__ == "JSONDecodeError"
