"""Unit tests for Remis Help Copilot helpers."""

from scripts.core.copilot.actions import filter_suggested_actions, list_actions
from scripts.core.copilot.context_budget import apply_context_budget, estimate_tokens
from scripts.core.copilot.help_pack import build_system_prompt, select_help_excerpts
from scripts.core.copilot.intents import build_capability_reply, detect_capability_intent
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


def test_select_help_excerpts_prefers_getting_started_for_first_run():
    excerpts, level, score = select_help_excerpts("第一次汉化该怎么走？")
    paths = [e["path"] for e in excerpts]
    assert any("getting-started" in p for p in paths)
    assert score > 0
    assert level in ("weak", "strong")
    assert all(e["content"] for e in excerpts)


def test_uncovered_topic_has_no_grounding():
    excerpts, level, score = select_help_excerpts("项目追踪这个功能是干什么用的？")
    assert excerpts == []
    assert level == "none"
    assert score == 0


def test_build_system_prompt_forces_low_when_uncovered():
    system, sources, grounding, score = build_system_prompt("项目追踪这个功能是干什么用的？")
    assert grounding == "none"
    assert sources == []
    assert "NONE" in system or "none" in system.lower()
    assert "禁止" in system
    assert score == 0


def test_build_system_prompt_includes_json_contract_for_api():
    system, sources, grounding, score = build_system_prompt("怎么配置 API 和 LM Studio")
    assert "suggested_actions" in system
    assert "open_api_settings" in system
    assert sources
    assert grounding in ("weak", "strong")
    assert score > 0


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
