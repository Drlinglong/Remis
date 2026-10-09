"""Apply verified model constraints after merging provider request parameters."""

from __future__ import annotations

import copy


OPENAI_REASONING_MODELS = {
    "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
    "gpt-6-astra", "gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna",
}
OPENAI_REASONING_SAMPLING_FIELDS = {
    "temperature", "top_p", "top_logprobs", "logprobs",
}
KIMI_K3_FIXED_FIELDS = {
    "temperature", "top_p", "n", "presence_penalty", "frequency_penalty",
}
ANTHROPIC_FIXED_SAMPLING_MODELS = {
    "claude-opus-5", "claude-sonnet-5",
    "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5",
}


def prepare_chat_request(provider_id: str, kwargs: dict) -> dict:
    """Filter incompatible fields in both SDK kwargs and its merged JSON body.

    Omitting built-in presets leaves the model's own reasoning default active.
    Only an explicit effective effort of ``none`` permits OpenAI sampling.
    Unknown models and other compatible endpoints retain their custom JSON.
    """
    prepared = copy.deepcopy(kwargs)
    extra_body = prepared.get("extra_body") or {}
    model = extra_body.get("model", prepared.get("model"))
    fields = set()
    if provider_id == "openai" and model in OPENAI_REASONING_MODELS:
        effort = extra_body.get("reasoning_effort", prepared.get("reasoning_effort"))
        if effort != "none":
            fields = OPENAI_REASONING_SAMPLING_FIELDS
    elif provider_id == "kimi" and model == "kimi-k3":
        fields = KIMI_K3_FIXED_FIELDS
    elif provider_id == "anthropic" and model in ANTHROPIC_FIXED_SAMPLING_MODELS:
        fields = {"temperature", "top_p", "top_k"}
    elif provider_id == "openrouter" and model in {
        "openai/gpt-5.6-luna", "openai/gpt-6-astra", "openai/gpt-6.1-sol",
        "openai/gpt-6-sol", "openai/gpt-6-luna",
    }:
        # These exact gateway routes do not advertise sampling parameters.
        fields = OPENAI_REASONING_SAMPLING_FIELDS
    for field in fields:
        prepared.pop(field, None)
        extra_body.pop(field, None)
    return prepared


def prepare_model_settings(provider_id: str, model: str, settings: dict) -> dict:
    """Apply the same sampling policy to PydanticAI's native effort setting."""
    request = prepare_chat_request(provider_id, {
        **settings,
        "model": model,
        "reasoning_effort": settings.get("openai_reasoning_effort"),
    })
    request.pop("model")
    request.pop("reasoning_effort")
    return request
