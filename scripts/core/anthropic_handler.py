import requests

from scripts.app_settings import get_api_key
from scripts.core.base_handler import BaseApiHandler


class AnthropicHandler(BaseApiHandler):
    """Anthropic Messages API handler."""

    API_VERSION = "2023-06-01"
    DEFAULT_SYSTEM_PROMPT = "You are a professional translator for game mods."

    def initialize_client(self) -> requests.Session:
        provider_config = self.get_provider_config()
        api_key_env = provider_config.get("api_key_env", "ANTHROPIC_API_KEY")
        api_key = get_api_key(self.provider_name, api_key_env)
        if not api_key:
            self.logger.error(
                "API key '%s' was not found for provider '%s'.",
                api_key_env,
                self.provider_name,
            )
            raise ValueError(f"{api_key_env} not set")

        self.base_url = provider_config.get(
            "base_url",
            "https://api.anthropic.com/v1",
        ).rstrip("/")

        session = requests.Session()
        session.headers.update(
            {
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": self.API_VERSION,
            }
        )
        return session

    @staticmethod
    def _extract_text(payload: dict) -> str:
        content = payload.get("content")
        if not isinstance(content, list):
            raise ValueError("Anthropic API response did not contain a content list.")

        text = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
        if not text:
            raise ValueError("Anthropic API response did not contain text content.")
        return text

    def _create_message(
        self,
        client: requests.Session,
        *,
        messages: list[dict],
        system: str,
        temperature: float | None = None,
    ) -> str:
        provider_config = self.get_provider_config()
        payload = {
            "model": provider_config.get("default_model", "claude-sonnet-4-5"),
            "max_tokens": 4000,
            "system": system,
            "messages": messages,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        response = client.post(
            f"{self.base_url}/messages",
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        return self._extract_text(response.json())

    def _call_api(self, client: requests.Session, prompt: str) -> str:
        return self._create_message(
            client,
            system=self.DEFAULT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

    def generate_with_messages(
        self,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> str:
        system_parts = []
        anthropic_messages = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                if content:
                    system_parts.append(content)
                continue
            if role in {"user", "assistant"} and content:
                anthropic_messages.append({"role": role, "content": content})

        if not anthropic_messages:
            raise ValueError("Anthropic messages must include user or assistant content.")

        return self._create_message(
            self.client,
            system="\n\n".join(system_parts) or self.DEFAULT_SYSTEM_PROMPT,
            messages=anthropic_messages,
            temperature=temperature,
        )
