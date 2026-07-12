"""Orchestrate Help Copilot chat: prompt + LLM + structured parse + action filter."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from scripts.core.api_handler import get_handler
from scripts.core.copilot.actions import filter_suggested_actions
from scripts.core.copilot.context_budget import (
    DEFAULT_INPUT_TOKEN_BUDGET,
    apply_context_budget,
)
from scripts.core.copilot.help_pack import build_system_prompt
from scripts.core.copilot.intents import build_capability_reply, detect_capability_intent
from scripts.schemas.copilot import (
    CopilotChatMessage,
    CopilotChatResponse,
    CopilotContextInfo,
    CopilotSource,
    SuggestedAction,
)

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

_HEDGING_RE = re.compile(
    r"(通常是|一般来说|一般是|根据.{0,12}逻辑|可能是指|应该是|大体上|多半是|我猜|推测)",
    re.IGNORECASE,
)


def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    candidate = text.strip()

    fence = _JSON_FENCE_RE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()

    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(candidate[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return None
    return None


def _last_user_text(messages: list[CopilotChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content.strip():
            return msg.content.strip()
    return messages[-1].content.strip() if messages else ""


def _history_for_model(messages: list[CopilotChatMessage]) -> list[dict[str, str]]:
    """Full user/assistant history; context_budget decides what survives."""
    return [
        {"role": m.role, "content": m.content}
        for m in messages
        if m.role in ("user", "assistant") and (m.content or "").strip()
    ]


def _clamp_confidence(
    confidence: str,
    *,
    grounding: str,
    reply: str,
    sources: list[Any],
) -> str:
    conf = (confidence or "medium").lower()
    if conf not in ("low", "medium", "high"):
        conf = "medium"

    if grounding == "none":
        return "low"

    if grounding == "policy":
        # Capability rules are product policy — allow medium/high.
        if conf not in ("low", "medium", "high"):
            return "high"
        return conf if conf in ("medium", "high") else "high"

    if grounding == "weak":
        # Weak match never deserves high; default to low unless model already low.
        if conf == "high":
            return "low"
        if conf == "medium":
            return "low"
        return "low"

    # Strong grounding: still demote obvious hedging / empty sources on high claims.
    if conf == "high" and (not sources or _HEDGING_RE.search(reply or "")):
        return "medium"
    return conf


def _filter_sources_for_grounding(
    sources: list[CopilotSource],
    allowed: list[dict[str, str]],
    grounding: str,
) -> list[CopilotSource]:
    if grounding in ("none", "policy"):
        # Policy answers are grounded in agent-operations, not user-guide paths.
        return []
    allowed_paths = {s["path"] for s in allowed}
    filtered = [s for s in sources if s.path in allowed_paths]
    if filtered:
        return filtered
    # Fall back to router-selected sources only when grounding is not none.
    return [CopilotSource(**s) for s in allowed]


def run_copilot_chat(
    messages: list[CopilotChatMessage],
    provider: str = "lm_studio",
    model: Optional[str] = None,
    locale: str = "zh",
    context_budget_tokens: int = DEFAULT_INPUT_TOKEN_BUDGET,
) -> CopilotChatResponse:
    if not messages:
        return CopilotChatResponse(
            reply="请先输入您的问题。",
            confidence="low",
            provider=provider,
            model=model,
            parse_mode="fallback_text",
            grounding="none",
        )

    user_query = _last_user_text(messages)

    # Capability / permission questions are product policy — answer without
    # keyword-doc routing and without the "文档未覆盖" path.
    capability = detect_capability_intent(user_query)
    if capability is not None:
        reply = build_capability_reply(capability, user_query)
        return CopilotChatResponse(
            reply=reply,
            suggested_actions=[SuggestedAction(**a) for a in capability.suggested_actions],
            sources=[],
            confidence=capability.confidence,  # type: ignore[arg-type]
            provider=(provider or "lm_studio").strip() or "lm_studio",
            model=(model or "").strip() or None,
            parse_mode="structured",
            grounding="policy",
            grounding_score=100,
            context=CopilotContextInfo(
                estimated_input_tokens=0,
                budget_tokens=context_budget_tokens or DEFAULT_INPUT_TOKEN_BUDGET,
                dropped_message_count=0,
                truncated_system=False,
                strategy="capability_short_circuit",
                warnings=["answered_from_agent_policy_without_llm"],
                history_message_count=0,
            ),
        )

    system_prompt, default_sources, grounding, grounding_score = build_system_prompt(
        user_query, locale=locale
    )

    history = _history_for_model(messages)
    budgeted = apply_context_budget(
        system_prompt,
        history,
        budget_tokens=context_budget_tokens or DEFAULT_INPUT_TOKEN_BUDGET,
    )
    context_info = CopilotContextInfo(**budgeted.as_dict())

    llm_messages: list[dict[str, str]] = [
        {"role": "system", "content": budgeted.system_prompt},
        *budgeted.history,
    ]

    provider_name = (provider or "lm_studio").strip() or "lm_studio"
    model_name = (model or "").strip() or None

    try:
        handler = get_handler(provider_name, model_name=model_name)
        raw = handler.generate_with_messages(llm_messages, temperature=0.2)
    except ConnectionError as exc:
        logger.error("Copilot LLM connection failed: %s", exc)
        return CopilotChatResponse(
            reply=(
                f"无法连接本地模型服务（{provider_name}）。\n\n"
                f"{exc}\n\n"
                "请确认 LM Studio 已启动并加载了模型，Base URL 一般为 "
                "`http://localhost:1234/v1`。之后可在小助手页面选择其他供应商。"
            ),
            suggested_actions=[
                SuggestedAction(
                    action="open_api_settings",
                    label="打开 API 设置",
                    risk="safe_ui_navigation",
                ),
                SuggestedAction(
                    action="open_log_folder",
                    label="打开日志文件夹",
                    risk="safe_ui_navigation",
                ),
            ],
            sources=[],
            confidence="low",
            provider=provider_name,
            model=model_name,
            parse_mode="fallback_text",
            grounding=grounding,  # type: ignore[arg-type]
            grounding_score=grounding_score,
            context=context_info,
        )
    except Exception as exc:
        logger.exception("Copilot LLM call failed")
        return CopilotChatResponse(
            reply=f"调用模型时出错：{exc}\n\n请检查本地 LM Studio 是否正常，或查看日志。",
            suggested_actions=[
                SuggestedAction(
                    action="open_log_folder",
                    label="打开日志文件夹",
                    risk="safe_ui_navigation",
                ),
            ],
            sources=[],
            confidence="low",
            provider=provider_name,
            model=model_name,
            parse_mode="fallback_text",
            grounding=grounding,  # type: ignore[arg-type]
            grounding_score=grounding_score,
            context=context_info,
        )

    parsed = _extract_json_object(raw or "")
    if not parsed:
        reply = (raw or "").strip() or "模型没有返回有效内容。请确认模型已加载。"
        if grounding == "none":
            reply = (
                "当前收录的用户文档里没有关于该问题的可靠说明，我不能凭猜测描述功能细节。\n\n"
                "您可以在左侧导航自行查看对应页面，或到 GitHub Issues 反馈文档缺失："
                " https://github.com/Drlinglong/Remis/issues"
            )
        return CopilotChatResponse(
            reply=reply,
            suggested_actions=(
                [
                    SuggestedAction(
                        action="open_github_issues",
                        label="打开 GitHub Issues",
                        risk="safe_ui_navigation",
                    )
                ]
                if grounding == "none"
                else []
            ),
            sources=[],
            confidence="low",
            provider=provider_name,
            model=model_name,
            parse_mode="fallback_text",
            grounding=grounding,  # type: ignore[arg-type]
            grounding_score=grounding_score,
            context=context_info,
        )

    reply = str(parsed.get("reply") or "").strip()
    if not reply:
        reply = (raw or "").strip() or "（空回复）"

    actions = filter_suggested_actions(parsed.get("suggested_actions"))
    sources_raw = parsed.get("sources")
    sources: list[CopilotSource] = []
    if isinstance(sources_raw, list):
        for item in sources_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            path = str(item.get("path") or "").strip()
            if title and path:
                sources.append(CopilotSource(title=title, path=path))

    sources = _filter_sources_for_grounding(sources, default_sources, grounding)

    confidence = _clamp_confidence(
        str(parsed.get("confidence") or "medium"),
        grounding=grounding,
        reply=reply,
        sources=sources,
    )

    # Extra guard: grounding none → always surface an honest disclaimer.
    if grounding == "none" and not reply.startswith(("当前收录的用户文档", "【文档未覆盖】")):
        reply = (
            "【文档未覆盖】当前用户指南中没有关于该问题的可靠说明，"
            "请不要把未经验证的推断当作官方功能说明。\n\n"
            + reply
        )
        confidence = "low"

    # If still none, prefer not suggesting unrelated navigations unless github.
    if grounding == "none":
        actions = [
            a
            for a in actions
            if a.get("action") in {"open_github_issues", "open_github_issue_132", "open_log_folder"}
        ]
        if not actions:
            actions = [
                {
                    "action": "open_github_issues",
                    "label": "打开 GitHub Issues",
                    "args": {},
                    "requires_confirmation": False,
                    "risk": "safe_ui_navigation",
                }
            ]

    if budgeted.dropped_message_count > 0:
        # Non-intrusive note for long threads (32k safety).
        note = (
            f"\n\n---\n_（上下文预算：已省略较早的 {budgeted.dropped_message_count} 条消息，"
            f"约 {budgeted.estimated_input_tokens}/{budgeted.budget_tokens} tokens）_"
        )
        if note.strip() not in reply:
            reply = reply.rstrip() + note

    return CopilotChatResponse(
        reply=reply,
        suggested_actions=[SuggestedAction(**a) for a in actions],
        sources=sources,
        confidence=confidence,  # type: ignore[arg-type]
        provider=provider_name,
        model=model_name,
        parse_mode="structured",
        grounding=grounding,  # type: ignore[arg-type]
        grounding_score=grounding_score,
        context=context_info,
    )
