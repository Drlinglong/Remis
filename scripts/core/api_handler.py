# scripts/core/api_handler.py
import logging
from typing import TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from .base_handler import BaseApiHandler

# --- Handler Imports ---
from .openai_handler import OpenAIHandler
from .gemini_handler import GeminiHandler
from .gemini_cli_handler import GeminiCLIHandler
from .qwen_handler import QwenHandler
from .deepseek_handler import DeepSeekHandler
from .grok_handler import GrokHandler
# from .ollama_handler import OllamaHandler # REMOVED
from .local_handler import LocalLLMHandler 
from .modelscope_handler import ModelScopeHandler
from .siliconflow_handler import SiliconFlowHandler
from .nvidia_handler import NvidiaHandler
from .hunyuan_handler import HunyuanHandler
from .yourfavourite_handler import YourFavouriteHandler


def get_handler(provider_name: str, model_name: str = None) -> 'BaseApiHandler':
    """
    【工厂函数】根据名称返回对应的API处理器实例。
    """
    try:
        if provider_name == "openai":
            return OpenAIHandler(provider_name, model_id=model_name)
        elif provider_name == "qwen":
            return QwenHandler(provider_name, model_id=model_name)
        elif provider_name == "gemini":
            return GeminiHandler(provider_name, model_id=model_name)
        elif provider_name == "gemini_cli":
            return GeminiCLIHandler(provider_name, model_name=model_name)
        elif provider_name == "deepseek":
            return DeepSeekHandler(provider_name, model_id=model_name)
        elif provider_name == "grok":
            return GrokHandler(provider_name, model_id=model_name)
        
        # Unified Local Handler Route
        elif provider_name in ["ollama", "lm_studio", "vllm", "koboldcpp", "oobabooga", "text-generation-webui"]:
            return LocalLLMHandler(provider_name, model_id=model_name)

        elif provider_name == "modelscope":
            return ModelScopeHandler(provider_name, model_id=model_name)
        elif provider_name == "siliconflow":
            return SiliconFlowHandler(provider_name, model_id=model_name)
        elif provider_name == "nvidia":
            return NvidiaHandler(provider_name, model_id=model_name)
        elif provider_name == "hunyuan":
            return HunyuanHandler(provider_name, model_id=model_name)
        elif provider_name == "your_favourite_api":
            return YourFavouriteHandler(provider_name, model_id=model_name)
        else:
            # 默认返回 Gemini
            logging.warning(f"Unknown provider '{provider_name}', falling back to 'gemini'.")
            return GeminiHandler("gemini", model_id=model_name)
    except Exception as e:
        logging.error(f"Failed to instantiate handler for {provider_name}: {e}", exc_info=True)
        raise
