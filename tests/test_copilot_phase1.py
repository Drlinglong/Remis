"""Unit tests for Remis Help Copilot helpers."""

from pathlib import Path

from scripts.core.copilot.actions import filter_suggested_actions, list_actions
from scripts.core.copilot.context_budget import apply_context_budget, estimate_tokens
from scripts.core.copilot.help_pack import (
    build_skill_router_prompt,
    build_system_prompt,
    build_native_tool_schema,
    build_native_skill_router_prompt,
    parse_skill_tool_calls,
    parse_native_tool_calls,
    read_help_skills,
    validate_help_skill_manifest,
)
from scripts.core.copilot.intents import build_capability_reply, detect_capability_intent
from scripts.core.copilot import service as copilot_service
from scripts.core.copilot.service import _clamp_confidence, _extract_json_object, run_copilot_chat
from scripts.schemas.copilot import CopilotChatMessage


def test_list_actions_excludes_none_and_is_phase1():
    actions = list_actions(phase=1)
    ids = {a["action"] for a in actions}
    assert "none" not in ids
    assert "open_project_management" in ids
    assert "open_api_settings" in ids
    assert "deploy_mod" not in ids
    assert "translate" not in ids


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
    assert cleaned[0]["label"] == "项目管理"


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
    assert sources
    assert grounding in ("weak", "strong")
    assert score > 0


def test_build_system_prompt_includes_read_only_page_context():
    system, _, _, _ = build_system_prompt(
        ["getting_started"],
        page_context={"pageId": "incremental-translation", "stepIndex": 2},
    )
    assert '"pageId": "incremental-translation"' in system
    assert '"stepIndex": 2' in system
    assert "不得声称已经替用户执行操作" in system


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
    class FakeHandler:
        def __init__(self):
            self.calls = []

        def generate_with_messages(self, messages, temperature=0.2):
            self.calls.append((messages, temperature))
            if len(self.calls) == 1:
                return (
                    '{"tool_calls":[{"name":"read_help_skill",'
                    '"arguments":{"skill_id":"provider_setup"}}]}'
                )
            return (
                '{"reply":"请检查 Ollama 地址和模型名。",'
                '"suggested_actions":[],"sources":'
                '[{"title":"Provider 配置","path":'
                '"zh/user-guides/provider-setup-index.md"}],"confidence":"high"}'
            )

        def select_tools_with_responses(
            self, messages, tools, tool_choice="auto", temperature=0.0
        ):
            self.calls.append((messages, tools))
            return [{"type": "function_call", "name": "read_help_skill", "arguments": '{"skill_id":"ollama_setup"}'}]

    fake = FakeHandler()
    monkeypatch.setattr(copilot_service, "get_handler", lambda *args, **kwargs: fake)
    result = run_copilot_chat(
        [
            CopilotChatMessage(role="user", content="Ollama 连接失败怎么办？"),
            CopilotChatMessage(role="assistant", content="我们继续排查。"),
            CopilotChatMessage(role="user", content="那具体怎么操作？"),
        ]
    )
    assert len(fake.calls) == 2
    assert result.grounding == "strong"
    assert any(source.path.endswith("using_ollama.md") for source in result.sources)
    assert result.context.routing_mode == "native_responses_tools"


def test_native_tool_schema_and_parser_are_allowlisted():
    schema = build_native_tool_schema()[0]
    assert "ollama_setup" in schema["parameters"]["properties"]["skill_id"]["enum"]
    calls = [
        {"name": "read_help_skill", "arguments": '{"skill_id":"settings"}'},
        {"name": "read_help_skill", "arguments": '{"skill_id":"not_allowed"}'},
    ]
    assert parse_native_tool_calls(calls) == ["settings"]
    assert build_native_tool_schema()[1]["name"] == "report_no_help_skill"


def test_native_router_prompt_does_not_request_json_text():
    prompt = build_native_skill_router_prompt()
    assert "不要输出 JSON" in prompt
    assert '"tool_calls"' not in prompt
    assert "必须使用提供的函数工具" in prompt


def test_every_packaged_user_guide_is_agent_selectable():
    assert validate_help_skill_manifest() == []


def test_release_and_debug_builds_bundle_help_skill_resources():
    root = Path(__file__).resolve().parents[1]
    pipeline = (root / "scripts" / "build_pipeline.py").read_text(encoding="utf-8")
    debug_build = (root / "debug_build.bat").read_text(encoding="utf-8")
    assert '"docs", "zh", "user-guides"' in pipeline
    assert "docs/zh/user-guides" in pipeline
    assert "docs\\zh\\user-guides;docs/zh/user-guides" in debug_build


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
