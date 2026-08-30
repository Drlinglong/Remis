"""Context-window budget for Copilot model requests.

Strategy (Phase 1.1):
- Estimate tokens with a CJK-aware heuristic (conservative).
- Prefer dropping oldest history turns over throwing errors.
- Never invent LLM summaries yet; only hard-trim history + cap system docs.
- Only fail hard if the *latest user message alone* cannot fit with a minimal system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# The default is deliberately a configurable input budget, not a claim about
# every provider/model window.  Provider metadata currently does not expose a
# verified limit that Remis can safely use here.
DEFAULT_INPUT_TOKEN_BUDGET = 200_000
MAX_INPUT_TOKEN_BUDGET = 200_000
MIN_INPUT_TOKEN_BUDGET = 2_000
# Keep at least the latest user turn even when history is huge.
MIN_RECENT_MESSAGES = 1
# Soft cap for how many recent turns we try to keep when budget allows.
DEFAULT_MAX_HISTORY_MESSAGES = 24

_CONTEXT_LIMIT_KEYS = (
    "context_window_tokens",
    "context_limit_tokens",
    "context_length",
    "max_context_tokens",
    "context_window",
    "max_context_length",
)


def verified_context_limit(
    provider_config: dict[str, Any] | None,
    model_name: str | None = None,
) -> int | None:
    """Return an explicitly declared provider/model context limit.

    We intentionally do not infer a limit from a model name, API family, or a
    remote models endpoint.  Those values are often stale or omit the
    provider's output reservation.  Only an integer in the dedicated metadata
    fields (or a model-specific entry under ``context_limits``) is reliable
    enough to constrain the local 200k default.
    """
    config = provider_config if isinstance(provider_config, dict) else {}
    candidates: list[Any] = []
    model_limits = config.get("context_limits")
    if model_name and isinstance(model_limits, dict):
        model_limit = model_limits.get(model_name)
        if isinstance(model_limit, dict):
            candidates.extend(model_limit.get(key) for key in _CONTEXT_LIMIT_KEYS)
        else:
            candidates.append(model_limit)
    candidates.extend(config.get(key) for key in _CONTEXT_LIMIT_KEYS)
    for candidate in candidates:
        if isinstance(candidate, bool):
            continue
        try:
            limit = int(candidate)
        except (TypeError, ValueError):
            continue
        if limit >= MIN_INPUT_TOKEN_BUDGET:
            return limit
    return None


def resolve_input_budget(
    requested_budget: int | None,
    *,
    provider_config: dict[str, Any] | None = None,
    model_name: str | None = None,
) -> int:
    """Resolve a request budget against optional verified model metadata."""
    requested = int(requested_budget or DEFAULT_INPUT_TOKEN_BUDGET)
    budget = min(MAX_INPUT_TOKEN_BUDGET, max(MIN_INPUT_TOKEN_BUDGET, requested))
    limit = verified_context_limit(provider_config, model_name)
    return min(budget, limit) if limit is not None else budget


def estimate_tokens(text: str) -> int:
    """Conservative token estimate for mixed Chinese / English prompts."""
    if not text:
        return 0
    cjk = 0
    other = 0
    for ch in text:
        code = ord(ch)
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0x3040 <= code <= 0x30FF
            or 0xAC00 <= code <= 0xD7AF
        ):
            cjk += 1
        else:
            other += 1
    # CJK often ≈ 1–1.5 tokens/char; ASCII ≈ 4 chars/token. Bias high.
    return max(1, int(cjk * 1.35 + other / 3.2) + 4)


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    total = 0
    for msg in messages:
        total += 4  # role / framing overhead
        total += estimate_tokens(str(msg.get("content") or ""))
    return total


@dataclass
class ContextBudgetResult:
    system_prompt: str
    history: list[dict[str, str]]
    estimated_input_tokens: int
    budget_tokens: int
    dropped_message_count: int = 0
    truncated_system: bool = False
    strategy: str = "keep_recent"
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "estimated_input_tokens": self.estimated_input_tokens,
            "budget_tokens": self.budget_tokens,
            "dropped_message_count": self.dropped_message_count,
            "truncated_system": self.truncated_system,
            "strategy": self.strategy,
            "warnings": list(self.warnings),
            "history_message_count": len(self.history),
        }


def _trim_text_to_tokens(text: str, max_tokens: int) -> str:
    if estimate_tokens(text) <= max_tokens:
        return text
    # Binary-search character cut (CJK-heavy → ~1 char/token upper bound).
    lo, hi = 0, len(text)
    best = ""
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = text[:mid].rstrip() + "\n\n…(上下文预算截断)"
        if estimate_tokens(candidate) <= max_tokens:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best or text[: max(200, max_tokens // 2)]


def apply_context_budget(
    system_prompt: str,
    history: list[dict[str, str]],
    *,
    budget_tokens: int = DEFAULT_INPUT_TOKEN_BUDGET,
    max_history_messages: int = DEFAULT_MAX_HISTORY_MESSAGES,
) -> ContextBudgetResult:
    """
    Fit system + history into budget_tokens.

    Drops oldest history first; may shrink system prompt if still over budget.
    Does **not** raise for normal long chats.
    """
    warnings: list[str] = []
    requested_budget = int(budget_tokens or DEFAULT_INPUT_TOKEN_BUDGET)
    budget = max(MIN_INPUT_TOKEN_BUDGET, requested_budget)
    if budget > MAX_INPUT_TOKEN_BUDGET:
        budget = MAX_INPUT_TOKEN_BUDGET
        warnings.append("budget_clamped_to_max")

    # Cap history length first (message count), then token budget.  The latest
    # user turn is selected from the complete input before applying this soft
    # cap; a run of persisted assistant messages must not hide that turn.
    original_count = len(history)
    latest_user_index = next(
        (index for index in range(original_count - 1, -1, -1) if history[index].get("role") == "user"),
        None,
    )
    if max_history_messages > 0 and original_count > max_history_messages:
        tail_indices = list(range(original_count - max_history_messages, original_count))
        if latest_user_index is not None and latest_user_index not in tail_indices:
            tail_indices = [latest_user_index, *tail_indices[:-1]]
            tail_indices.sort()
        capped = [history[index] for index in tail_indices]
    else:
        capped = list(history)
    dropped = original_count - len(capped)

    system = system_prompt or ""
    # Reserve room for the most recent user message.  A provider may return a
    # trailing assistant message in persisted history, but that must not make
    # the user's latest question eligible for oldest-history trimming.
    protected_index = next(
        (index for index in range(len(capped) - 1, -1, -1) if capped[index].get("role") == "user"),
        len(capped) - 1,
    ) if capped else 0
    protected = capped[protected_index] if capped else {"role": "user", "content": ""}
    last_tokens = estimate_messages_tokens([protected])
    system_cap = max(1_500, budget - last_tokens - 256)
    truncated_system = False
    if estimate_tokens(system) > system_cap:
        system = _trim_text_to_tokens(system, system_cap)
        truncated_system = True
        warnings.append("system_prompt_truncated_for_budget")

    # Drop oldest until under budget, while always retaining the protected
    # latest user message.  Normally the protected message is last and this is
    # the usual oldest-first path; trailing assistant messages are dropped only
    # when retaining the latest user requires it.
    while len(capped) > MIN_RECENT_MESSAGES:
        total = estimate_tokens(system) + estimate_messages_tokens(capped)
        if total <= budget:
            break
        if protected_index > 0:
            capped.pop(0)
            protected_index -= 1
        else:
            capped.pop(1)
        dropped += 1

    total = estimate_tokens(system) + estimate_messages_tokens(capped)
    strategy = "keep_recent"
    if dropped:
        strategy = "drop_oldest_history"
        warnings.append(f"dropped_{dropped}_older_messages")

    # If still over (huge latest message), trim that message content.
    if total > budget and capped:
        remaining = max(256, budget - estimate_tokens(system) - 32)
        trimmed = dict(capped[protected_index])
        trimmed["content"] = _trim_text_to_tokens(str(trimmed.get("content") or ""), remaining)
        capped[protected_index] = trimmed
        total = estimate_tokens(system) + estimate_messages_tokens(capped)
        strategy = "trim_latest_user_message"
        warnings.append("latest_user_message_truncated")

    if total > budget:
        warnings.append("still_over_budget_after_trim")

    return ContextBudgetResult(
        system_prompt=system,
        history=capped,
        estimated_input_tokens=total,
        budget_tokens=budget,
        dropped_message_count=dropped,
        truncated_system=truncated_system,
        strategy=strategy,
        warnings=warnings,
    )
