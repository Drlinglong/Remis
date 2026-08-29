"""Remis Help Copilot: lightweight exports and lazy model-backed services."""

from .actions import ACTION_REGISTRY, filter_suggested_actions, list_actions
from .context_budget import (
    DEFAULT_INPUT_TOKEN_BUDGET,
    apply_context_budget,
    resolve_input_budget,
    verified_context_limit,
)
from .intents import detect_capability_intent


def run_copilot_chat(*args, **kwargs):
    """Load the model-backed service only when the hidden Copilot API is called."""
    from .service import run_copilot_chat as _run_copilot_chat

    return _run_copilot_chat(*args, **kwargs)

__all__ = [
    "ACTION_REGISTRY",
    "DEFAULT_INPUT_TOKEN_BUDGET",
    "apply_context_budget",
    "resolve_input_budget",
    "verified_context_limit",
    "detect_capability_intent",
    "filter_suggested_actions",
    "list_actions",
    "run_copilot_chat",
]
