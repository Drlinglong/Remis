# scripts/core/api_handler.py
import logging
from typing import TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from .base_handler import BaseApiHandler

# --- Handler Imports ---
from .openai_handler import OpenAIHandler
from .anthropic_handler import AnthropicHandler
from .gemini_handler import GeminiHandler
from .qwen_handler import QwenHandler
from .deepseek_handler import DeepSeekHandler
from .openrouter_handler import OpenRouterHandler
from .grok_handler import GrokHandler
# from .ollama_handler import OllamaHandler # REMOVED
from .local_handler import LocalLLMHandler 
from .modelscope_handler import ModelScopeHandler
from .siliconflow_handler import SiliconFlowHandler
from .nvidia_handler import NvidiaHandler
from .hunyuan_handler import HunyuanHandler
from .yourfavourite_handler import YourFavouriteHandler


OPENAI_COMPATIBLE_PROVIDER_IDS = {
    "openai",
    "kimi",
    "minimax",
    "zhipu",
}

LOCAL_PROVIDER_IDS = {
    "ollama",
    "lm_studio",
    "vllm",
    "koboldcpp",
    "oobabooga",
    "text-generation-webui",
}

PROVIDER_HANDLER_CLASSES = {
    "anthropic": AnthropicHandler,
    "gemini": GeminiHandler,
    "qwen": QwenHandler,
    "deepseek": DeepSeekHandler,
    "openrouter": OpenRouterHandler,
    "grok": GrokHandler,
    "modelscope": ModelScopeHandler,
    "siliconflow": SiliconFlowHandler,
    "nvidia": NvidiaHandler,
    "hunyuan": HunyuanHandler,
    "your_favourite_api": YourFavouriteHandler,
}

SUPPORTED_PROVIDER_IDS = (
    set(PROVIDER_HANDLER_CLASSES)
    | OPENAI_COMPATIBLE_PROVIDER_IDS
    | LOCAL_PROVIDER_IDS
)


def get_handler(
    provider_name: str,
    model_name: str = None,
    reasoning_override: dict | None = None,
    provider_config_snapshot: dict | None = None,
    api_key_override: str | None = None,
) -> 'BaseApiHandler':
    """
    【工厂函数】根据名称返回对应的API处理器实例。
    """
    try:
        if provider_name == "gemini_cli":
            raise ValueError(
                "The Gemini CLI provider has been removed. Use the Gemini API provider with GEMINI_API_KEY instead."
            )
        handler_kwargs = {"model_id": model_name}
        if reasoning_override is not None:
            handler_kwargs["reasoning_override"] = reasoning_override
        if provider_config_snapshot is not None:
            handler_kwargs["provider_config_snapshot"] = provider_config_snapshot
        if api_key_override is not None:
            handler_kwargs["api_key_override"] = api_key_override
        if provider_name in OPENAI_COMPATIBLE_PROVIDER_IDS:
            return OpenAIHandler(provider_name, **handler_kwargs)
        if provider_name in LOCAL_PROVIDER_IDS:
            return LocalLLMHandler(provider_name, **handler_kwargs)
        handler_class = PROVIDER_HANDLER_CLASSES.get(provider_name)
        if handler_class is None:
            raise ValueError(f"Unknown API provider: {provider_name}")
        return handler_class(provider_name, **handler_kwargs)
    except Exception as e:
        logging.error(f"Failed to instantiate handler for {provider_name}: {e}", exc_info=True)
        raise
