# scripts/core/local_handler.py
import os
import requests
import logging
from typing import Any
from urllib.parse import urlsplit
from openai import APIConnectionError, OpenAI

from scripts.core.base_handler import BaseApiHandler


def _append_system_suffix(system_prompt: str, provider_config: dict) -> str:
    suffix = (provider_config.get("system_prompt_suffix") or "").strip()
    if not suffix or system_prompt.rstrip().endswith(suffix):
        return system_prompt
    return f"{system_prompt.rstrip()} {suffix}"


class LocalLLMHandler(BaseApiHandler):
    """
    Unified Handler for all Local LLMs.
    "Wear one pair of pants" - Handles both Native Ollama API and OpenAI-Compatible Local APIs.
    """

    OPENAI_ENDPOINT_SUFFIXES = ("/chat/completions", "/responses")
    PROVIDER_DISPLAY_NAMES = {
        "lm_studio": "LM Studio",
        "vllm": "vLLM",
        "koboldcpp": "KoboldCpp",
        "oobabooga": "Oobabooga",
        "text-generation-webui": "Text Generation WebUI",
        "ollama": "Ollama",
    }

    def _connection_error_message(self) -> str:
        provider_name = self.PROVIDER_DISPLAY_NAMES.get(
            self.provider_name,
            self.provider_name.replace("_", " ").title(),
        )
        return (
            f"无法连接 {provider_name}：Remis 正在访问 {self.base_url}。"
            "请检查本地服务是否已启动，并确认端口设置正确。"
        )

    @classmethod
    def _validate_openai_base_url(cls, raw_url: str) -> str:
        """Validate that the user supplied a base URL, not a concrete endpoint."""
        url = (raw_url or "http://localhost:1234/v1").strip().rstrip("/")
        parsed = urlsplit(url)
        path = parsed.path.rstrip("/").lower()

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "Invalid local OpenAI-compatible API Base URL. "
                "Use a full base URL such as http://localhost:1234/v1."
            )

        if any(path.endswith(suffix) for suffix in cls.OPENAI_ENDPOINT_SUFFIXES):
            raise ValueError(
                "Invalid local OpenAI-compatible API Base URL. "
                "Enter the service base URL, not a concrete endpoint. "
                "For LM Studio, use http://localhost:1234/v1 instead of "
                f"{url}."
            )

        return url

    def initialize_client(self) -> Any:
        provider_config = self.get_provider_config()
        self.protocol = "openai" # Default to OpenAI-compatible
        
        # 1. Determine Protocol based on Provider Name
        if self.provider_name == "ollama":
            self.protocol = "ollama"
        
        # 2. Configure Base URL
        if self.protocol == "ollama":
            self.base_url = os.getenv("OLLAMA_BASE_URL", provider_config.get("base_url", "http://localhost:11434"))
            self._check_ollama_version()
            # For Ollama, the 'client' is just the config itself usually, but we return self to match pattern
            return self
        else:
            # For LM Studio, vLLM, etc.
            base_url_env = provider_config.get("base_url_env")
            raw_base_url = (
                os.getenv(base_url_env, "") if base_url_env else ""
            ) or provider_config.get("base_url", "http://localhost:1234/v1")
            self.base_url = self._validate_openai_base_url(raw_base_url)
            
            # Dummy Key for local services that don't need it
            api_key = provider_config.get("api_key", "local-no-key-required")
            
            try:
                client = OpenAI(api_key=api_key, base_url=self.base_url)
                model_name = provider_config.get("default_model", "local-model")
                self.logger.info(f"[{self.provider_name}] Local OpenAI-Compatible Client initialized. URL: {self.base_url}, Model: {model_name}")
                return client
            except Exception as e:
                self.logger.exception(f"Error initializing Local Client for {self.provider_name}: {e}")
                raise

    def _check_ollama_version(self):
        try:
            response = requests.get(f"{self.base_url}/api/version", timeout=10)
            response.raise_for_status()
            version_str = response.json().get("version", "0.0.0")
            # Simple version check logic...
            self.logger.info(f"Ollama Version: {version_str}")
        except Exception as e:
            self.logger.warning(f"Could not verify Ollama version at {self.base_url}: {e}")

    def _call_api(self, client: Any, prompt: str) -> str:
        """Dispatches call based on protocol."""
        if self.protocol == "ollama":
            return self._call_ollama_native(prompt)
        else:
            return self._call_openai_compatible(client, prompt)

    @staticmethod
    def _extract_chat_content(response: Any, model_name: str, base_url: str) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise ValueError(
                "Local OpenAI-compatible API returned no chat choices. "
                "Check that the base URL is an OpenAI chat base such as "
                f"http://localhost:1234/v1; current base URL: {base_url}"
            )

        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        finish_reason = getattr(choices[0], "finish_reason", None)
        reasoning_content = (getattr(message, "reasoning_content", None) or "").strip()
        tool_calls = getattr(message, "tool_calls", None) or []

        if not content and tool_calls:
            raise ValueError(
                "Local OpenAI-compatible model returned tool calls instead of translation text. "
                "Disable tool/function calling for this local model or choose a plain chat/translation model."
            )
        if not content and reasoning_content:
            if finish_reason == "length":
                raise ValueError(
                    "Local OpenAI-compatible model returned reasoning-only output and hit the context/output limit. "
                    f"Model '{model_name}' produced reasoning_content but no final chat content. "
                    "Disable thinking/reasoning for this model, increase LM Studio context/output limits, or reduce batch size."
                )
            raise ValueError(
                "Local OpenAI-compatible model returned reasoning_content but no final chat content. "
                "Disable thinking/reasoning for this model or use a model that writes translations to message.content."
            )
        if not content:
            raise ValueError(
                "Local OpenAI-compatible API returned an empty chat message. "
                f"Model '{model_name}' may not be loaded, or the endpoint at {base_url} is not serving chat completions."
            )
        return content.strip()

    def generate_with_messages(self, messages: list[dict], temperature: float = 0.7) -> str:
        """Preserve the complete conversation so structured repair prompts can see prior output."""
        if self.protocol == "ollama":
            conversation = "\n\n".join(
                f"{message.get('role', 'user').upper()}:\n{message.get('content', '')}"
                for message in messages
            )
            return self._call_ollama_native(conversation)

        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "local-model")
        prepared_messages = [dict(message) for message in messages]
        suffix = provider_config.get("system_prompt_suffix")
        if suffix:
            for message in prepared_messages:
                if message.get("role") == "system":
                    message["content"] = _append_system_suffix(message.get("content", ""), provider_config)
                    break
        try:
            request_kwargs = {
                "model": model_name,
                "messages": prepared_messages,
                "temperature": temperature,
            }
            response = self.client.chat.completions.create(
                **self._apply_reasoning_to_openai_kwargs(request_kwargs)
            )
            return self._extract_chat_content(response, model_name, self.base_url)
        except APIConnectionError as exc:
            message = self._connection_error_message()
            self.logger.error(message)
            raise ConnectionError(message) from exc

    def _call_ollama_native(self, prompt: str) -> str:
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "llama2")
        
        try:
            # Handle prompt splitting if needed (legacy Ollama logic)
            system_prompt = _append_system_suffix(
                "You are a professional translator for game mods.",
                provider_config,
            )
            user_prompt = prompt
            if "--- INPUT LIST ---" in prompt:
                 parts = prompt.split("--- INPUT LIST ---", 1)
                 if len(parts) == 2:
                     system_prompt = _append_system_suffix(parts[0], provider_config)
                     user_prompt = parts[1]
                     user_prompt = "--- INPUT LIST ---" + user_prompt

            payload = {
                "model": model_name,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
            }
            payload.update(self._reasoning_request_parameters())

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=300
            )
            
            if response.status_code == 404:
                 # Check for 'model not found'
                 try:
                     err = response.json().get('error')
                     if err: raise ValueError(f"Ollama Error: {err}. Try pulling model '{model_name}'.")
                 except: pass

            response.raise_for_status()
            return response.json().get("response", "").strip()

        except requests.ConnectionError as e:
            message = self._connection_error_message()
            self.logger.error(message)
            raise ConnectionError(message) from e
        except Exception as e:
            self.logger.exception(f"Ollama Native API call failed: {e}")
            raise

    def _call_openai_compatible(self, client: OpenAI, prompt: str) -> str:
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "local-model")
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": _append_system_suffix(
                        "You are a professional translator for game mods.",
                        provider_config,
                    ),
                },
                {"role": "user", "content": prompt}
            ]
            
            request_kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.3,
            }
            response = client.chat.completions.create(
                **self._apply_reasoning_to_openai_kwargs(request_kwargs)
            )
            return self._extract_chat_content(response, model_name, self.base_url)
        except APIConnectionError as e:
            message = self._connection_error_message()
            self.logger.error(message)
            raise ConnectionError(message) from e
        except Exception as e:
             # Check for context length error message in the exception string or checking type if imported
             error_str = str(e).lower()
             if "context length" in error_str or "context size has been exceeded" in error_str:
                 self.logger.error("Context Length Exceeded! The prompt is too long for the current model configuration.")
                 self.logger.error("SUGGESTION: Increase context length in LM Studio/vLLM (e.g., to 8192) or reduce 'chunk_size' in config.")
             
             self.logger.exception(f"Local OpenAI-Compatible API call failed: {e}")
             raise
