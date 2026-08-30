"""Unit tests for Remis Help Copilot helpers."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.core.copilot.actions import filter_suggested_actions, list_actions
from scripts.core.copilot.context_budget import (
    DEFAULT_INPUT_TOKEN_BUDGET,
    apply_context_budget,
    estimate_tokens,
    resolve_input_budget,
)
from scripts.core.copilot.help_pack import (
    build_skill_router_prompt,
    build_system_prompt,
    parse_skill_tool_calls,
    read_help_skills,
    validate_help_skill_manifest,
)
from scripts.core.copilot import help_agent_models
from scripts.core.copilot.help_agent_models import build_help_model, supports_pydantic_help_agent
from scripts.core.copilot.help_agent import HelpAnswer
from scripts.core.copilot.intents import build_capability_reply, detect_capability_intent
from scripts.core.copilot.workflow_entities import canonicalize_workflow_entities
from scripts.core.copilot import service as copilot_service
from scripts.core.copilot.service import _clamp_confidence, _extract_json_object, run_copilot_chat
from scripts.app_settings import API_PROVIDERS
from scripts.schemas.copilot import CopilotChatMessage
from scripts.routers.copilot import copilot_actions, copilot_status


def test_list_actions_excludes_none_and_is_phase1():
    actions = list_actions(phase=1)
    ids = {a["action"] for a in actions}
    assert "none" not in ids
    assert "open_project_management" in ids
    assert "open_api_settings" in ids
    assert "deploy_mod" not in ids
    assert "translate" not in ids
    assert "start_localization_workflow" not in ids


def test_workflow_action_is_available_in_phase2_and_requires_server_plan():
    actions = list_actions(phase=2)
    item = next(action for action in actions if action["action"] == "start_localization_workflow")
    assert item["risk"] == "read_only_until_approval"
    assert copilot_status().phase == 2
    assert any(item.action == "start_localization_workflow" for item in copilot_actions())


def test_filter_suggested_actions_whitelist_and_dedupe():
    raw = [
        {"action": "open_project_management", "label": "项目管理"},
        {"action": "deploy_mod", "label": "部署"},
        {"action": "open_project_management", "label": "重复"},
        {"action": "none"},
        {"action": "totally_fake"},
        {"action": "open_log_folder"},
    ]
    cleaned = filter_suggested_actions(raw)
    assert [c["action"] for c in cleaned] == [
        "open_project_management",
        "open_log_folder",
    ]
    assert cleaned[0]["label"] == "打开项目管理"


def test_action_registry_owns_security_metadata_and_validates_args():
    cleaned = filter_suggested_actions([
        {
            "action": "open_initial_translation",
            "label": "删除全部文件",
            "requires_confirmation": False,
            "risk": "harmless",
            "args": {"project_id": "project-1", "arbitrary_path": "../../secrets"},
        }
    ])
    assert cleaned == [{
        "action": "open_initial_translation",
        "label": "打开初次翻译",
        "args": {},
        "requires_confirmation": False,
        "risk": "safe_ui_navigation",
    }]


def test_localization_action_rejects_incomplete_or_untrusted_workflow_hints():
    assert filter_suggested_actions([{
        "action": "start_localization_workflow",
        "args": {},
    }]) == []

    cleaned = filter_suggested_actions([{
        "action": "start_localization_workflow",
        "args": {
            "project_mode": "new",
            "folder_path": r"C:\\Mods\\Victoria",
            "project_name": "Victoria Demo",
            "game_id": "vic3",
            "source_language": "en",
            "target_languages": ["zh-CN"],
            "api_provider": "openrouter",
            "model": "openai/gpt-5.6-luna",
            "api_key": "must-not-pass",
        },
    }])
    assert cleaned == []

    assert filter_suggested_actions([{
        "action": "start_localization_workflow",
        "args": {
            "project_mode": "existing",
            "project_name": "Project Remis - Demo Mod - Stellaris",
            "target_languages": ["zh-CN"],
        },
    }]) == []


def test_localization_action_accepts_complete_new_project_inputs():
    cleaned = filter_suggested_actions([{
        "action": "start_localization_workflow",
        "args": {
            "project_mode": "new",
            "folder_path": r"C:\\Mods\\Victoria",
            "project_name": "Victoria Demo",
            "game_id": "vic3",
            "source_language": "en",
            "target_languages": ["zh-CN", "zh-CN", "ja"],
            "api_provider": "openrouter",
            "model": "openai/gpt-5.6-luna",
        },
    }])
    assert cleaned[0]["args"] == {
        "project_mode": "new",
        "folder_path": r"C:\\Mods\\Victoria",
        "project_name": "Victoria Demo",
        "game_id": "vic3",
        "source_language": "en",
        "target_languages": ["zh-CN", "ja"],
        "api_provider": "openrouter",
        "model": "openai/gpt-5.6-luna",
    }


def test_localization_action_accepts_existing_project_and_shared_model_defaults():
    cleaned = filter_suggested_actions([{
        "action": "start_localization_workflow",
        "args": {
            "project_mode": "existing",
            "project_id": "project-1",
            "project_name": "Project Remis - Demo Mod - Stellaris",
            "target_language": "zh-CN",
        },
    }], workflow_defaults={
        "api_provider": "openrouter",
        "model": "openai/gpt-5.6-luna",
    })
    assert cleaned[0]["args"] == {
        "project_mode": "existing",
        "project_id": "project-1",
        "project_name": "Project Remis - Demo Mod - Stellaris",
        "target_languages": ["zh-CN"],
        "api_provider": "openrouter",
        "model": "openai/gpt-5.6-luna",
    }


def test_workflow_entities_resolve_semantic_provider_model_to_canonical_ids():
    catalog = {
        "projects": [{
            "project_id": "project-1",
            "name": "Project Remis - Demo Mod - Stellaris",
            "game_id": "stellaris",
            "source_language": "en",
        }],
        "providers": [{
            "id": "openrouter",
            "name": "OpenRouter",
            "models": ["openai/gpt-5.6-luna"],
        }],
    }
    cleaned = filter_suggested_actions([{
        "action": "start_localization_workflow",
        "args": {
            "project_mode": "existing",
            "project_name": "Project Remis Demo Mod Stellaris",
            "target_languages": ["zh-CN"],
            "api_provider": "OpenRouter",
            "model": "gpt 5.6luna",
        },
    }], workflow_entity_catalog=catalog)
    assert cleaned[0]["args"]["project_id"] == "project-1"
    assert cleaned[0]["args"]["project_name"] == "Project Remis - Demo Mod - Stellaris"
    assert cleaned[0]["args"]["api_provider"] == "openrouter"
    assert cleaned[0]["args"]["model"] == "openai/gpt-5.6-luna"


def test_workflow_entities_fail_closed_on_ambiguous_project_or_unknown_model():
    catalog = {
        "projects": [
            {"project_id": "one", "name": "Same Project"},
            {"project_id": "two", "name": "Same Project"},
        ],
        "providers": [{"id": "openrouter", "name": "OpenRouter", "models": ["model-a"]}],
    }
    assert canonicalize_workflow_entities({
        "project_mode": "existing",
        "project_name": "Same Project",
        "api_provider": "openrouter",
        "model": "model-a",
    }, catalog) is None
    assert canonicalize_workflow_entities({
        "project_mode": "new",
        "api_provider": "openrouter",
        "model": "invented-model",
    }, catalog) is None


def test_incomplete_workflow_does_not_hide_later_complete_duplicate():
    cleaned = filter_suggested_actions([
        {"action": "start_localization_workflow", "args": {}},
        {"action": "start_localization_workflow", "args": {
            "project_mode": "existing",
            "project_name": "Exact project name",
            "target_languages": ["zh-CN"],
            "api_provider": "openrouter",
            "model": "openai/gpt-5.6-luna",
        }},
    ])
    assert len(cleaned) == 1
    assert cleaned[0]["args"]["project_name"] == "Exact project name"


def test_extract_json_object_handles_fence_and_noise():
    fenced = """Here you go:
```json
{"reply": "你好", "suggested_actions": [], "confidence": "high"}
```
"""
    data = _extract_json_object(fenced)
    assert data["reply"] == "你好"
    assert data["confidence"] == "high"


def test_agent_tool_calls_are_allowlisted_deduplicated_and_capped():
    raw = """{
      "tool_calls": [
        {"name":"read_help_skill","arguments":{"skill_id":"provider_setup"}},
        {"name":"read_help_skill","arguments":{"skill_id":"totally_fake"}},
        {"name":"read_help_skill","arguments":{"skill_id":"provider_setup"}},
        {"name":"read_help_skill","arguments":{"skill_id":"logs_and_errors"}},
        {"name":"read_help_skill","arguments":{"skill_id":"deployment"}},
        {"name":"read_help_skill","arguments":{"skill_id":"glossary"}}
      ]
    }"""
    assert parse_skill_tool_calls(raw) == [
        "provider_setup",
        "logs_and_errors",
        "deployment",
    ]


def test_read_help_skill_reads_full_allowlisted_resource():
    excerpts = read_help_skills(["getting_started"])
    assert excerpts
    assert excerpts[0]["path"] == "zh/user-guides/getting-started.md"
    assert "创建" in excerpts[0]["content"]


def test_steam_workshop_guide_is_agent_selectable():
    excerpts = read_help_skills(["steam_workshop"])
    assert excerpts
    assert excerpts[0]["path"] == "zh/user-guides/steam-workshop.md"
    assert "发布工作区" in excerpts[0]["content"]


def test_build_system_prompt_forces_low_when_agent_selects_no_skill():
    system, sources, grounding, score = build_system_prompt([])
    assert grounding == "none"
    assert sources == []
    assert "NONE" in system or "none" in system.lower()
    assert "禁止" in system
    assert score == 0


def test_build_system_prompt_includes_json_contract_for_api():
    system, sources, grounding, score = build_system_prompt(["provider_setup"])
    assert "suggested_actions" in system
    assert "open_api_settings" in system
    assert "手动操作指导" in system
    assert "资料不完整时只追问缺失项" in system
    assert "project_mode" in system
    assert "target_languages" in system
    assert sources
    assert grounding in ("weak", "strong")
    assert score > 0


def test_build_system_prompt_includes_read_only_page_context():
    system, _, _, _ = build_system_prompt(
        ["getting_started"],
        page_context={"pageId": "incremental-translation", "helpSkillId": "incremental_translation", "stepIndex": 2},
    )
    assert '"pageId": "incremental-translation"' in system
    assert '"helpSkillId": "incremental_translation"' in system
    assert '"stepIndex": 2' in system
    assert "不得声称已经替用户执行操作" in system


def test_build_system_prompt_includes_safe_workflow_entity_catalog():
    system, _, _, _ = build_system_prompt(
        ["getting_started"],
        workflow_entity_catalog={
            "projects": [{"project_id": "project-1", "name": "Stellaris Demo"}],
            "providers": [{"id": "openrouter", "models": ["openai/gpt-5.6-luna"]}],
            "secrets_exposed": False,
        },
    )
    assert '"project_id": "project-1"' in system
    assert '"id": "openrouter"' in system
    assert "API Key" in system


def test_router_prompt_receives_recent_conversation_for_followups():
    history = [
        {"role": "user", "content": "Ollama 连接失败怎么办？"},
        {"role": "assistant", "content": "我可以读取 Provider 帮助。"},
        {"role": "user", "content": "那具体怎么操作？"},
    ]
    prompt = build_skill_router_prompt(history)
    assert "Ollama 连接失败" in prompt
    assert "那具体怎么操作" in prompt
    assert "read_help_skill" in prompt


def test_chat_uses_agent_selected_skill_for_ambiguous_followup(monkeypatch):
    from types import SimpleNamespace

    captured = {}
    monkeypatch.setattr(copilot_service, "run_pydantic_help_agent", lambda history, **kwargs: (
        captured.update({"history": history, **kwargs}) or {
            "answer": SimpleNamespace(
                reply="请检查 Ollama 地址和模型名。", suggested_actions=[], confidence="high"
            ),
            "selected_skill_ids": ["provider_setup"],
            "excerpts": [{
                "title": "Provider 配置",
                "path": "zh/user-guides/provider-setup-index.md",
                "content": "x",
            }],
            "no_match_reason": None,
            "usage": {},
        }
    ))
    result = run_copilot_chat(
        [
            CopilotChatMessage(role="user", content="Ollama 连接失败怎么办？"),
            CopilotChatMessage(role="assistant", content="我们继续排查。"),
            CopilotChatMessage(role="user", content="那具体怎么操作？"),
        ],
        provider="ollama",
    )
    assert captured["history"][-1]["content"] == "那具体怎么操作？"
    assert result.grounding == "strong"
    assert any(source.path.endswith("provider-setup-index.md") for source in result.sources)
    assert result.context.routing_mode == "pydantic_ai_tools"


def test_lm_studio_help_chat_uses_pydantic_agent_and_canonical_actions(monkeypatch):
    from types import SimpleNamespace

    fake_answer = SimpleNamespace(
        reply="请先创建项目。",
        suggested_actions=[SimpleNamespace(model_dump=lambda: {
            "action": "open_create_project", "args": {}, "label": "evil"
        })],
        confidence="high",
    )
    monkeypatch.setattr(copilot_service, "run_pydantic_help_agent", lambda *args, **kwargs: {
        "answer": fake_answer,
        "selected_skill_ids": ["getting_started"],
        "excerpts": [{"title": "从零开始", "path": "zh/user-guides/getting-started.md", "content": "x"}],
        "no_match_reason": None,
        "usage": {},
    })
    result = run_copilot_chat(
        [CopilotChatMessage(role="user", content="我要汉化一个 Mod")],
        provider="lm_studio",
    )
    assert result.context.strategy == "pydantic_ai_help_agent"
    assert result.suggested_actions[0].label == "去创建新项目"
    assert result.sources[0].path == "zh/user-guides/getting-started.md"


def test_lm_studio_help_chat_drops_premature_workflow_action(monkeypatch):
    from types import SimpleNamespace

    fake_answer = SimpleNamespace(
        reply="你希望手动操作，还是由 Agent 帮你规划？",
        suggested_actions=[SimpleNamespace(model_dump=lambda: {
            "action": "start_localization_workflow", "args": {},
        })],
        confidence="high",
    )
    monkeypatch.setattr(copilot_service, "run_pydantic_help_agent", lambda *args, **kwargs: {
        "answer": fake_answer,
        "selected_skill_ids": ["getting_started"],
        "excerpts": [{"title": "从零开始", "path": "zh/user-guides/getting-started.md", "content": "x"}],
        "no_match_reason": None,
        "usage": {},
    })
    result = run_copilot_chat(
        [CopilotChatMessage(role="user", content="第一次汉化该怎么走？")],
        provider="lm_studio",
        model="local-model",
    )
    assert result.suggested_actions == []
    assert "手动操作" in result.reply


def test_lm_studio_help_agent_failure_is_visible_and_recoverable(monkeypatch):
    monkeypatch.setattr(
        copilot_service,
        "run_pydantic_help_agent",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("planner timed out")),
    )
    result = run_copilot_chat(
        [CopilotChatMessage(role="user", content="怎么创建项目？")],
        provider="lm_studio",
    )
    assert result.confidence == "low"
    assert result.parse_mode == "fallback_text"
    assert "TimeoutError" in result.context.warnings
    assert "暂时无法" in result.reply


def test_native_cloud_copilot_uses_tool_agent(monkeypatch):
    from types import SimpleNamespace

    captured = {}
    monkeypatch.setattr(
        copilot_service,
        "run_pydantic_help_agent",
        lambda *args, **kwargs: captured.update(kwargs) or {
            "answer": SimpleNamespace(reply="Cloud tool route used.", suggested_actions=[], confidence="high"),
            "selected_skill_ids": ["provider_setup"],
            "excerpts": [{"title": "Provider 配置", "path": "zh/user-guides/provider-setup-index.md", "content": "x"}],
            "no_match_reason": None,
            "usage": {},
        },
    )

    result = run_copilot_chat(
        [CopilotChatMessage(role="user", content="How do I configure a provider?")],
        provider="gemini",
        model="gemini-3.7-flash",
    )

    assert result.reply == "Cloud tool route used."
    assert captured["provider"] == "gemini"
    assert result.context.routing_mode == "pydantic_ai_tools"


def test_openrouter_help_chat_uses_pydantic_tools(monkeypatch):
    from types import SimpleNamespace

    fake_answer = SimpleNamespace(reply="已找到唯一项目。", suggested_actions=[], confidence="high")
    captured = {}
    monkeypatch.setattr(copilot_service, "build_workflow_entity_catalog", lambda: {
        "projects": [{"project_id": "project-1", "name": "Stellaris Demo"}],
        "providers": [{"id": "openrouter", "name": "OpenRouter", "models": ["openai/gpt-5.6-luna"]}],
    })
    monkeypatch.setattr(copilot_service, "run_pydantic_help_agent", lambda *args, **kwargs: (
        captured.update(kwargs) or {
            "answer": fake_answer,
            "selected_skill_ids": ["getting_started"],
            "excerpts": [{"title": "从零开始", "path": "zh/user-guides/getting-started.md", "content": "x"}],
            "no_match_reason": None,
            "usage": {},
        }
    ))
    result = run_copilot_chat(
        [CopilotChatMessage(role="user", content="帮我规划群星 demo mod")],
        provider="openrouter",
        model="openai/gpt-5.6-luna",
    )
    assert result.context.routing_mode == "pydantic_ai_tools"
    assert captured["provider"] == "openrouter"
    assert captured["workflow_entity_catalog"]["projects"][0]["project_id"] == "project-1"


def test_every_configured_provider_enters_the_tool_agent_path():
    assert {provider for provider in API_PROVIDERS if supports_pydantic_help_agent(provider)} == set(API_PROVIDERS)


@pytest.mark.parametrize("provider", list(API_PROVIDERS))
def test_provider_factory_constructs_tool_model_without_network(monkeypatch, provider):
    monkeypatch.setattr(help_agent_models, "get_api_key", lambda *_args: "test-only-placeholder")
    expected_model = API_PROVIDERS[provider]["default_model"]
    model, settings, selected_model = build_help_model(provider, expected_model, {})
    assert model is not None
    assert settings["parallel_tool_calls"] is True
    assert selected_model == expected_model


def test_provider_factory_rejects_missing_key_before_network(monkeypatch):
    monkeypatch.setattr(help_agent_models, "get_api_key", lambda *_args: "")
    with pytest.raises(RuntimeError, match="provider_not_configured"):
        build_help_model("openrouter", "openai/gpt-5.6-luna", {})


def test_typed_help_output_rejects_empty_workflow_args():
    with pytest.raises(ValidationError):
        HelpAnswer.model_validate({
            "reply": "已经准备好计划",
            "suggested_actions": [{"action": "start_localization_workflow", "args": {}}],
            "confidence": "high",
        })


def test_tool_unsupported_error_is_actionable_and_does_not_fallback(monkeypatch):
    monkeypatch.setattr(
        copilot_service,
        "run_pydantic_help_agent",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("This model does not support tools")
        ),
    )
    result = run_copilot_chat(
        [CopilotChatMessage(role="user", content="帮我规划")],
        provider="openrouter",
        model="openai/gpt-5.6-luna",
    )
    assert result.parse_mode == "fallback_text"
    assert "工具调用" in result.reply
    assert "没有降级执行" in result.reply


def test_context_length_failure_is_explicitly_recoverable(monkeypatch):
    monkeypatch.setattr(
        copilot_service,
        "run_pydantic_help_agent",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("maximum context length exceeded")
        ),
    )

    result = run_copilot_chat(
        [CopilotChatMessage(role="user", content="请回答这个问题")],
        provider="gemini",
        model="gemini-3.7-flash",
    )

    assert result.confidence == "low"
    assert "可恢复" in result.reply
    assert "上下文长度" in result.reply


def test_every_packaged_user_guide_is_agent_selectable():
    assert validate_help_skill_manifest() == []


def test_release_and_debug_builds_bundle_help_skill_resources():
    root = Path(__file__).resolve().parents[1]
    pipeline = (root / "scripts" / "build_pipeline.py").read_text(encoding="utf-8")
    debug_build = (
        root / "scripts" / "developer_tools" / "windows" / "debug_build.bat"
    ).read_text(encoding="utf-8")
    assert '"docs", "zh", "user-guides"' in pipeline
    assert "docs/zh/user-guides" in pipeline
    assert "docs\\zh\\user-guides;docs/zh/user-guides" in debug_build
    assert "--collect-submodules pydantic_ai" in pipeline
    assert "--copy-metadata pydantic-ai-slim" in pipeline
    assert "--collect-submodules pydantic_ai" in debug_build
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    assert "pydantic-ai-slim[anthropic,google,openai,openrouter]==2.9.0" in requirements


def test_clamp_confidence_none_and_weak():
    assert _clamp_confidence("high", grounding="none", reply="x", sources=[]) == "low"
    assert _clamp_confidence("medium", grounding="weak", reply="x", sources=[]) == "low"
    assert _clamp_confidence("high", grounding="strong", reply="文档写明了步骤", sources=["a"]) == "high"


def test_context_budget_drops_oldest_instead_of_error():
    history = [
        {"role": "user", "content": f"问题 {i} " + ("汉化流程说明。" * 80)}
        for i in range(40)
    ]
    # Alternate assistant replies
    full = []
    for i, user in enumerate(history):
        full.append(user)
        full.append({"role": "assistant", "content": f"回答 {i} " + ("步骤。" * 40)})

    system = "系统提示 " + ("文档片段。" * 200)
    result = apply_context_budget(system, full, budget_tokens=4000, max_history_messages=40)
    assert result.dropped_message_count > 0
    assert result.estimated_input_tokens <= result.budget_tokens + 50  # small slack for framing
    assert len(result.history) >= 1
    assert result.history[-1]["role"] in ("user", "assistant")
    assert "drop" in result.strategy or result.dropped_message_count > 0


def test_context_budget_default_is_200k_and_protects_latest_user_after_assistant_tail():
    history = [
        {"role": "user", "content": "最重要的最后用户问题"},
        *[
            {"role": "assistant", "content": f"旧的持久化回答 {index} " + ("文本。" * 50)}
            for index in range(30)
        ],
    ]

    result = apply_context_budget("", history, budget_tokens=2_000, max_history_messages=6)

    assert DEFAULT_INPUT_TOKEN_BUDGET == 200_000
    assert any(message["content"] == "最重要的最后用户问题" for message in result.history)
    assert result.history[0]["role"] == "user"


def test_context_budget_drops_oldest_messages_before_newer_messages():
    history = [
        {"role": "user", "content": f"message-{index} " + ("x" * 5000)}
        for index in range(8)
    ]

    result = apply_context_budget("", history, budget_tokens=1_500, max_history_messages=20)

    assert result.dropped_message_count > 0
    assert result.history[-1]["content"].startswith("message-7")
    assert all("message-0" not in item["content"] for item in result.history)


def test_context_budget_uses_only_explicit_provider_limit():
    assert resolve_input_budget(200_000, provider_config={"name": "OpenAI"}) == 200_000
    assert resolve_input_budget(
        200_000,
        provider_config={"context_limits": {"known-model": 32_000}},
        model_name="known-model",
    ) == 32_000


def test_estimate_tokens_positive():
    assert estimate_tokens("hello") > 0
    assert estimate_tokens("第一次汉化") > estimate_tokens("ab")


def test_detect_cannot_edit_mod_files_intent():
    intent = detect_capability_intent(
        "我需要你帮我修改一份不太满意的mod文件，你能帮我吗？"
    )
    assert intent is not None
    assert intent.intent_id == "cannot_edit_mod_files"
    reply = build_capability_reply(intent)
    assert "没有权限" in reply
    assert "无法" in reply
    assert "【文档未覆盖】" not in reply


def test_capability_short_circuit_does_not_call_docs_none_path():
    # No LM Studio needed: policy short-circuit.
    result = run_copilot_chat(
        [
            CopilotChatMessage(
                role="user",
                content="我需要你帮我修改一份不太满意的mod文件，你能帮我吗？",
            )
        ],
        provider="lm_studio",
    )
    assert result.grounding == "policy"
    assert result.confidence == "high"
    assert "没有权限" in result.reply
    assert "【文档未覆盖】" not in result.reply
    assert result.context is not None
    assert result.context.strategy == "capability_short_circuit"
