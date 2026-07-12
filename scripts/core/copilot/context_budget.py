"""Context-window budget for local models (e.g. 32k).

Strategy (Phase 1.1):
- Estimate tokens with a CJK-aware heuristic (conservative).
- Prefer dropping oldest history turns over throwing errors.
- Never invent LLM summaries yet; only hard-trim history + cap system docs.
- Only fail hard if the *latest user message alone* cannot fit with a minimal system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Leave headroom for model output + provider overhead on a 32k window.
DEFAULT_INPUT_TOKEN_BUDGET = 24_000
# Keep at least the latest user turn even when history is huge.
MIN_RECENT_MESSAGES = 1
# Soft cap for how many recent turns we try to keep when budget allows.
DEFAULT_MAX_HISTORY_MESSAGES = 24


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
    budget = max(2_000, int(budget_tokens or DEFAULT_INPUT_TOKEN_BUDGET))

    # Cap history length first (message count), then token budget.
    original_count = len(history)
    capped = list(history[-max_history_messages:]) if max_history_messages > 0 else list(history)
    dropped = original_count - len(capped)

    system = system_prompt or ""
    # Reserve room for at least the last user message.
    last = capped[-1] if capped else {"role": "user", "content": ""}
    last_tokens = estimate_messages_tokens([last])
    system_cap = max(1_500, budget - last_tokens - 256)
    truncated_system = False
    if estimate_tokens(system) > system_cap:
        system = _trim_text_to_tokens(system, system_cap)
        truncated_system = True
        warnings.append("system_prompt_truncated_for_budget")

    # Drop oldest until under budget (keep at least MIN_RECENT_MESSAGES).
    while len(capped) > MIN_RECENT_MESSAGES:
        total = estimate_tokens(system) + estimate_messages_tokens(capped)
        if total <= budget:
            break
        capped.pop(0)
        dropped += 1

    total = estimate_tokens(system) + estimate_messages_tokens(capped)
    strategy = "keep_recent"
    if dropped:
        strategy = "drop_oldest_history"
        warnings.append(f"dropped_{dropped}_older_messages")

    # If still over (huge latest message), trim that message content.
    if total > budget and capped:
        remaining = max(256, budget - estimate_tokens(system) - 32)
        trimmed = dict(capped[-1])
        trimmed["content"] = _trim_text_to_tokens(str(trimmed.get("content") or ""), remaining)
        capped = capped[:-1] + [trimmed]
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
