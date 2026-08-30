"""Runtime helpers for model-arena provider snapshots and handler calls."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable, Optional

from scripts import app_settings
from scripts.core.services.model_arena_execution_service import (
    ArenaContestant,
    ArenaHandlerCompletion,
)


SYSTEM_INSTRUCTION = "You are a professional translator for game mods."
LOCAL_PROVIDER_IDS = {
    "ollama",
    "lm_studio",
    "vllm",
    "koboldcpp",
    "oobabooga",
    "text-generation-webui",
}


def safe_provider_snapshot(provider_id: str, model_id: str) -> dict[str, Any]:
    base = dict(app_settings.API_PROVIDERS.get(provider_id, {}))
    overrides = dict(
        app_settings.config_manager.get_value("provider_config", {}).get(provider_id, {})
    )
    allowed = {
        "enable_thinking",
        "max_tokens",
        "reasoning_effort",
        "temperature",
        "top_p",
    }
    parameters = {
        key: value
        for key, value in {**base, **overrides}.items()
        if key in allowed and isinstance(value, (bool, int, float, str))
    }
    system_instruction = "" if provider_id == "gemini" else SYSTEM_INSTRUCTION
    suffix = str(overrides.get("system_prompt_suffix") or "").strip()
    if suffix and provider_id in LOCAL_PROVIDER_IDS:
        system_instruction = f"{system_instruction.rstrip()} {suffix}"
    return {
        "provider_id": provider_id,
        "model_id": model_id,
        "parameters": parameters,
        "system_instruction": system_instruction,
    }


class ProductionArenaHandler:
    """Adapter that records the exact production prompt before parsing."""

    def __init__(
        self,
        handler: Any,
        prompt_text: str,
        system_instruction: str,
        effective_parameters: Mapping[str, Any],
    ) -> None:
        self._handler = handler
        self._prompt_text = prompt_text
        self._system_instruction = system_instruction
        self._effective_parameters = dict(effective_parameters)

    def execute_model_arena_request(
        self,
        *,
        system_instruction: Optional[str],
        user_prompt: str,
        effective_parameters: Mapping[str, Any],
    ) -> ArenaHandlerCompletion:
        del user_prompt
        prompt = self._prompt_text
        completion = self._handler._call_api(self._handler.client, prompt)
        return ArenaHandlerCompletion(
            completion_text_before_parse=completion,
            completion_source=getattr(
                self._handler, "last_completion_source", "assistant_content"
            ),
            system_instruction=system_instruction or self._system_instruction,
            user_prompt=prompt,
            effective_parameters={
                **self._effective_parameters,
                **dict(effective_parameters),
            },
        )

    def _parse_response(
        self, completion: str, source_texts: list[str], target_lang_code: str
    ) -> Any:
        return self._handler._parse_response(
            completion, source_texts, target_lang_code
        )


def build_handler_factory(
    handler_factory: Callable[..., Any],
    snapshots: Mapping[str, Mapping[str, Any]],
    prompt_text: str,
) -> Callable[[ArenaContestant], ProductionArenaHandler]:
    def factory(contestant: ArenaContestant) -> ProductionArenaHandler:
        handler = handler_factory(
            contestant.provider_name,
            model_name=contestant.model_id,
            provider_config_snapshot=dict(
                snapshots.get(contestant.contestant_id, {})
            ),
        )
        return ProductionArenaHandler(
            handler,
            prompt_text,
            contestant.system_instruction or SYSTEM_INSTRUCTION,
            contestant.effective_parameters,
        )

    return factory
