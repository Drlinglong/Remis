import os
import logging
from typing import Any
from google import genai
from google.genai import types

from scripts.app_settings import API_PROVIDERS
from scripts.core.base_handler import BaseApiHandler

class GeminiHandler(BaseApiHandler):
    """Gemini API Handler子类"""

    def _generate_content(self, client: Any, **kwargs):
        try:
            return client.models.generate_content(**kwargs, http_options={'timeout': 300})
        except TypeError as exc:
            if "http_options" not in str(exc):
                raise
            self.logger.warning(
                "Installed google-genai SDK does not support http_options on generate_content; retrying without it."
            )
            return client.models.generate_content(**kwargs)

    def initialize_client(self) -> Any:
        """【必须由子类实现】初始化并配置Gemini的API客户端。"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.logger.error("API Key 'GEMINI_API_KEY' not found in environment variables.")
            raise ValueError("GEMINI_API_KEY not set")
        try:
            # The genai.configure() method is deprecated.
            # The API key is now passed directly to the genai.Client constructor.
            client = genai.Client(api_key=api_key)
            self.logger.info("Gemini client initialized successfully.")
            return client
        except Exception as e:
            self.logger.exception(f"Error initializing Gemini client: {e}")
            raise

    def _call_api(self, client: Any, prompt: str) -> str:
        """【必须由子类实现】执行对Gemini API的调用并返回原始文本响应。"""
        provider_config = self.get_provider_config()
        model_name = provider_config.get("default_model", "gemini-1.5-flash")
        
        enable_thinking = provider_config.get("enable_thinking", False)
        thinking_budget = provider_config.get("thinking_budget", 0)

        generation_config = {}
        if enable_thinking:
            # According to latest google-genai docs:
            # Gemini 3 models support thinking_level ('low', 'high', 'medium', 'minimal')
            # Gemini 2.5 models use thinking_budget
            
            # Map user's desire: For Gemini 3, 'low' is requested.
            is_gemini_3 = "gemini-3" in model_name
            
            if is_gemini_3:
                # The SDK uses ThinkingConfig for both.
                generation_config["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_level="low" # User specifically requested 'low' for Gemini 3
                )
            elif thinking_budget != 0:
                generation_config["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=True
                )
                # For Gemini 2.x, thinking_budget is the field. 
                # Note: If the SDK supports setting budget on ThinkingConfig, we'd do it here.
                # Many implementations pass thinking_budget as a top-level field in GenerateContentConfig.
                if thinking_budget > 0:
                    generation_config["thinking_budget"] = thinking_budget

        try:
            # Pass the generation_config to the API call
            response = self._generate_content(
                client,
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**generation_config) if generation_config else None,
            )
            
            # SAFE EXTRACTION: Avoid the 'thought_signature' warning by extracting only text parts
            # Response parts can contain Text, Thought, Call, etc.
            if response.candidates and response.candidates[0].content.parts:
                text_parts = [part.text for part in response.candidates[0].content.parts if part.text]
                if text_parts:
                    return "".join(text_parts).strip()
            
            # Fallback to .text if parts extraction fails (will trigger warning but at least returns something)
            return response.text.strip()
        except Exception as e:
            self.logger.exception(f"Gemini API call failed: {e}")
            raise

    def generate_with_messages(self, messages: list[dict], temperature: float = 0.7) -> str:
        """
        Supports chat-like interaction for NeologismMiner.
        """
        provider_config = API_PROVIDERS.get(self.provider_name, {})
        model_name = provider_config.get("default_model", "gemini-1.5-flash")
        
        # Convert messages to Gemini format if needed, or just concatenate for now
        # Gemini client supports chat history, but for single turn we can just use generate_content
        # with system instruction if supported, or just prompt engineering.
        
        # Extract system prompt
        system_instruction = None
        user_content = ""
        
        for msg in messages:
            if msg['role'] == 'system':
                system_instruction = msg['content']
            elif msg['role'] == 'user':
                user_content += msg['content'] + "\n"
        
        try:
            # New Gemini API supports system_instruction in generation_config or client.models.generate_content
            # Let's try passing it in config or as argument if supported by library version
            # Based on google-genai library, it might be 'config'
            
            # Simple fallback: Prepend system prompt
            full_prompt = user_content
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{user_content}"
            
            response = self._generate_content(
                self.client,
                model=model_name,
                contents=full_prompt,
                config={
                    'temperature': temperature
                },
            )
            return response.text.strip()
        except Exception as e:
            self.logger.exception(f"Gemini chat generation failed: {e}")
            return ""
