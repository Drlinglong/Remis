"""Orchestrate Help Copilot chat: prompt + LLM + structured parse + action filter."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from scripts.app_settings import API_PROVIDERS, config_manager
from scripts.core.api_handler import get_handler
from scripts.core.copilot.actions import filter_suggested_actions
from scripts.core.copilot.context_budget import (
    DEFAULT_INPUT_TOKEN_BUDGET,
    apply_context_budget,
    resolve_input_budget,
)
from scripts.core.copilot.help_pack import (
    build_skill_router_prompt,
    build_system_prompt,
    parse_skill_tool_calls,
)
from scripts.core.copilot.intents import build_capability_reply, detect_capability_intent
from scripts.core.copilot.help_agent import run_pydantic_help_agent
from scripts.core.copilot.runtime import resolve_provider_runtime_snapshot
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot
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


def _is_context_length_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "context length",
            "context size",
            "maximum context",
            "prompt is too long",
            "too many tokens",
            "token limit",
        )
    )


def _provider_error_reply(provider: str, model: str | None, error: Exception) -> str:
    if _is_context_length_error(error):
        return (
            f"供应商 {provider} / {model or '默认模型'} 拒绝了当前上下文长度。\n\n"
            "这是可恢复的上下文长度错误：请重试以丢弃更早的聊天消息，或在“设置 → 小助手设置”中选择"
            "已知上下文更大的模型；Remis 不会要求您粘贴 API Key。"
        )
    return (
        f"调用 {provider} / {model or '默认模型'} 时出错：{error}\n\n"
        "请检查“小助手设置”中的供应商与模型、对应 API 配置，或查看日志。"
    )


def resolve_copilot_context_budget(
    provider: str,
    model: str | None,
    requested_budget: int | None,
    provider_runtime: ProviderRuntimeSnapshot | None = None,
) -> int:
    if provider_runtime is not None:
        provider_config = provider_runtime.config
    else:
        provider_config = dict(API_PROVIDERS.get(provider, {}))
        provider_overrides = config_manager.get_value("provider_config", {}) or {}
        if isinstance(provider_overrides, dict):
            provider_config.update(provider_overrides.get(provider, {}) or {})
    return resolve_input_budget(
        requested_budget,
        provider_config=provider_config,
        model_name=model or provider_config.get("selected_model") or provider_config.get("default_model"),
    )


def _help_agent_error_reply(provider: str, model: str | None, error: Exception) -> str:
    if _is_context_length_error(error):
        return _provider_error_reply(provider, model, error)
    return f"小助手暂时无法完成这次回答：{error}"


def _connection_error_reply(provider: str, model: str | None, error: Exception) -> str:
    if _is_context_length_error(error):
        return _provider_error_reply(provider, model, error)
    return (
        f"无法连接本地模型服务（{provider}）。\n\n"
        f"{error}\n\n"
        "请确认 LM Studio 已启动并加载了模型，Base URL 一般为 "
        "`http://localhost:1234/v1`。之后可在小助手页面选择其他供应商。"
    )


def _capability_response(
    capability: Any,
    query: str,
    provider: str,
    model: str | None,
    budget: int,
) -> CopilotChatResponse:
    return CopilotChatResponse(
        reply=build_capability_reply(capability, query),
        suggested_actions=[SuggestedAction(**a) for a in capability.suggested_actions],
        confidence=capability.confidence,  # type: ignore[arg-type]
        provider=provider,
        model=model,
        grounding="policy",
        grounding_score=100,
        context=CopilotContextInfo(
            budget_tokens=budget,
            strategy="capability_short_circuit",
            warnings=["answered_from_agent_policy_without_llm"],
        ),
    )


def _empty_chat_response(
    provider: str,
    model: str | None,
) -> CopilotChatResponse:
    return CopilotChatResponse(
        reply="请先输入您的问题。",
        confidence="low",
        provider=provider,
        model=model,
        parse_mode="fallback_text",
        grounding="none",
    )


def _prepare_copilot_request(
    provider: str,
    model: str | None,
    context_budget_tokens: int,
    reasoning_override: dict[str, Any] | None,
    provider_runtime: ProviderRuntimeSnapshot | None,
) -> tuple[ProviderRuntimeSnapshot, str, str | None, int]:
    requested_provider = (provider or "lm_studio").strip() or "lm_studio"
    requested_model = (model or "").strip() or None
    runtime = provider_runtime or resolve_provider_runtime_snapshot(
        requested_provider,
        requested_model,
        reasoning_override=reasoning_override,
    )
    provider_name = runtime.selection_id
    model_name = runtime.model_id
    budget = resolve_copilot_context_budget(
        provider_name,
        model_name,
        context_budget_tokens,
        provider_runtime=runtime,
    )
    return runtime, provider_name, model_name, budget


def run_copilot_chat(
    messages: list[CopilotChatMessage],
    provider: str = "lm_studio",
    model: Optional[str] = None,
    locale: str = "zh",
    context_budget_tokens: int = DEFAULT_INPUT_TOKEN_BUDGET,
    page_context: Optional[dict[str, Any]] = None,
    reasoning_override: Optional[dict[str, Any]] = None,
    provider_runtime: ProviderRuntimeSnapshot | None = None,
) -> CopilotChatResponse:
    runtime, provider_name, model_name, effective_budget = _prepare_copilot_request(
        provider,
        model,
        context_budget_tokens,
        reasoning_override,
        provider_runtime,
    )
    if not messages:
        return _empty_chat_response(provider_name, model_name)

    user_query = _last_user_text(messages)
    # Capability / permission questions are product policy — answer without
    # keyword-doc routing and without the "文档未覆盖" path.
    capability = detect_capability_intent(user_query)
    if capability is not None:
        return _capability_response(
            capability, user_query, provider_name, model_name, effective_budget
        )

    history = _history_for_model(messages)
    grounding = "none"
    grounding_score = 0
    context_info = CopilotContextInfo(
        budget_tokens=effective_budget,
        strategy="agent_skill_routing",
        history_message_count=len(history),
    )
    budgeted = None

    if provider_name == "lm_studio":
        try:
            budgeted = apply_context_budget("", history, budget_tokens=effective_budget)
            started = time.perf_counter()
            agent_result = run_pydantic_help_agent(
                budgeted.history,
                model_name=model_name,
                page_context=page_context,
                reasoning_override=reasoning_override,
                provider_runtime=runtime,
            )
            answer = agent_result["answer"]
            excerpts = agent_result["excerpts"]
            selected_skill_ids = agent_result["selected_skill_ids"]
            default_sources = [{"title": item["title"], "path": item["path"]} for item in excerpts]
            grounding = "strong" if excerpts else "none"
            grounding_score = 100 if excerpts else 0
            actions = filter_suggested_actions(
                [item.model_dump() for item in answer.suggested_actions]
            )
            sources = [CopilotSource(**item) for item in default_sources]
            confidence = _clamp_confidence(
                answer.confidence, grounding=grounding, reply=answer.reply, sources=sources
            )
            reply = answer.reply
            if grounding == "none" and not reply.startswith("【文档未覆盖】"):
                reply = "【文档未覆盖】" + reply
            context_info = CopilotContextInfo(**budgeted.as_dict())
            context_info.strategy = "pydantic_ai_help_agent"
            context_info.routing_mode = "pydantic_ai_tools"
            context_info.routing_ms = round((time.perf_counter() - started) * 1000)
            context_info.selected_skill_ids = selected_skill_ids
            context_info.loaded_source_count = len(sources)
            return CopilotChatResponse(
                reply=reply,
                suggested_actions=[SuggestedAction(**item) for item in actions],
                sources=sources,
                confidence=confidence,  # type: ignore[arg-type]
                provider=provider_name,
                model=model_name,
                parse_mode="structured",
                grounding=grounding,  # type: ignore[arg-type]
                grounding_score=grounding_score,
                context=context_info,
            )
        except Exception as exc:
            logger.exception("PydanticAI Help Copilot failed")
            return CopilotChatResponse(
                reply=_help_agent_error_reply(provider_name, model_name, exc),
                confidence="low",
                provider=provider_name,
                model=model_name,
                parse_mode="fallback_text",
                grounding="none",
                context=CopilotContextInfo(
                    budget_tokens=effective_budget,
                    strategy="pydantic_ai_help_agent_failed",
                    warnings=(budgeted.warnings if budgeted else []) + [type(exc).__name__],
                    history_message_count=len(history),
                ),
            )

    try:
        handler = get_handler(
            runtime.adapter_id,
            model_name=runtime.model_id,
            reasoning_override=reasoning_override,
            **runtime.handler_kwargs(),
        )
        route_started = time.perf_counter()
        router_messages = [
            {"role": "system", "content": build_skill_router_prompt(history, locale)},
            *history[-8:],
        ]
        router_raw = handler.generate_with_messages(router_messages, temperature=0.0)
        selected_skill_ids = parse_skill_tool_calls(router_raw or "")
        routing_mode = "compatibility_json"
        routing_ms = round((time.perf_counter() - route_started) * 1000)

        system_prompt, default_sources, grounding, grounding_score = build_system_prompt(
            selected_skill_ids, locale=locale, page_context=page_context
        )
        budgeted = apply_context_budget(
            system_prompt,
            history,
            budget_tokens=effective_budget,
        )
        context_info = CopilotContextInfo(**budgeted.as_dict())
        context_info.routing_mode = routing_mode
        context_info.routing_ms = routing_ms
        context_info.selected_skill_ids = selected_skill_ids
        context_info.loaded_source_count = len(default_sources)
        if not selected_skill_ids:
            context_info.warnings.append("agent_selected_no_help_skills")

        llm_messages: list[dict[str, str]] = [
            {"role": "system", "content": budgeted.system_prompt},
            *budgeted.history,
        ]
        answer_started = time.perf_counter()
        raw = handler.generate_with_messages(llm_messages, temperature=0.2)
        context_info.answer_ms = round((time.perf_counter() - answer_started) * 1000)
    except ConnectionError as exc:
        logger.error("Copilot LLM connection failed: %s", exc)
        return CopilotChatResponse(
            reply=_connection_error_reply(provider_name, model_name, exc),
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
            reply=_provider_error_reply(provider_name, model_name, exc),
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

    if budgeted is not None and budgeted.dropped_message_count > 0:
        # Non-intrusive note for long threads after the 200k/default budget.
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
