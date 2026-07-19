"""Capability / policy intents that are grounded in agent-operations, not user-guides.

These are answered from fixed product rules. The model does **not** browse the repo;
keyword routing only selects user-guide excerpts for product-how-to questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CapabilityIntent:
    intent_id: str
    # Used as grounding label in API/UI
    grounding: str = "policy"
    confidence: str = "high"
    suggested_actions: tuple[dict, ...] = ()


# Phrases that mean "please edit my files / mod content for me".
_EDIT_FILE_PATTERNS = [
    r"帮我修[改订]",
    r"帮我编辑",
    r"帮我改",
    r"替我改",
    r"直接改",
    r"修改一份",
    r"修改.*(?:mod|模组|文件|yml|yaml|txt)",
    r"(?:edit|modify|change|fix).*(?:mod|file|yml)",
    r"can you (?:edit|modify|change|fix)",
    r"帮我改一下",
    r"改一下.*(?:文件|mod|模组)",
    r"编辑.*(?:mod|模组|文件)",
    r"重写.*(?:文件|mod)",
    r"没有权限",  # rare self-ask
]

# Explicit "do you have permission / can you write files"
_PERMISSION_PATTERNS = [
    r"有没有权限",
    r"能否.*(?:修改|编辑|写入)",
    r"可以.*(?:直接修改|直接编辑|改文件)",
    r"能不能.*(?:改文件|改mod|改模组)",
    r"(?:write|edit).*(?:permission|disk|file)",
]

# Ask to change Remis itself / source code
_EDIT_REMIS_PATTERNS = [
    r"改.*remis.*源码",
    r"修改.*客户端",
    r"打补丁",
    r"改软件",
    r"patch remis",
    r"modify remis source",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def detect_capability_intent(user_query: str) -> Optional[CapabilityIntent]:
    q = (user_query or "").strip()
    if not q:
        return None
    # Normalize full-width punctuation a bit
    q_norm = q.replace("？", "?").replace("！", "!")

    if _matches_any(q_norm, _EDIT_REMIS_PATTERNS):
        return CapabilityIntent(
            intent_id="cannot_edit_remis_client",
            confidence="high",
            suggested_actions=(
                {
                    "action": "open_github_issues",
                    "label": "打开 GitHub Issues",
                    "args": {},
                    "requires_confirmation": False,
                    "risk": "safe_ui_navigation",
                },
            ),
        )

    if _matches_any(q_norm, _EDIT_FILE_PATTERNS) or _matches_any(q_norm, _PERMISSION_PATTERNS):
        # If clearly about translation quality only, still refuse direct file edit,
        # but point to proofreading / workshop.
        translation_hint = bool(
            re.search(r"翻译|译文|汉化|localisation|localization|translation", q_norm, re.I)
        )
        actions: list[dict] = []
        if translation_hint:
            actions.extend(
                [
                    {
                        "action": "open_proofreading",
                        "label": "打开校对",
                        "args": {},
                        "requires_confirmation": False,
                        "risk": "safe_ui_navigation",
                    },
                    {
                        "action": "open_agent_workshop",
                        "label": "打开智能工坊",
                        "args": {},
                        "requires_confirmation": False,
                        "risk": "safe_ui_navigation",
                    },
                ]
            )
        return CapabilityIntent(
            intent_id="cannot_edit_mod_files",
            confidence="high",
            suggested_actions=tuple(actions),
        )

    return None


def build_capability_reply(intent: CapabilityIntent, user_query: str = "") -> str:
    """Deterministic policy replies — do not depend on user-guide keyword hits."""
    _ = user_query
    if intent.intent_id == "cannot_edit_remis_client":
        return (
            "我**不能**修改 Remis 客户端或源代码。\n\n"
            "您使用的是打包好的 Remis，小助手没有改程序的权限，也不会在聊天里“打补丁”。\n\n"
            "如果这是功能需求或 Bug，请到 GitHub 反馈，由维护者处理：\n"
            "https://github.com/Drlinglong/Remis/issues"
        )

    # cannot_edit_mod_files (default)
    return (
        "我**没有权限**直接帮您修改或编辑 Mod 文件，因此无法在聊天里替您改磁盘上的内容。\n\n"
        "当前阶段的 Remis 小助手只能：\n"
        "1. 根据用户文档说明如何使用 Remis；\n"
        "2. 建议您点击安全的页面跳转（设置、项目管理、日志等）。\n\n"
        "它**不能**：\n"
        "- 打开并改写您的 yml / 脚本 / 其他 Mod 文件；\n"
        "- 替您改游戏逻辑或代码；\n"
        "- 在未走客户端确认流程的情况下执行写盘操作。\n\n"
        "如果您其实想优化**译文**，请在 Remis 里用「校对」手动修改，"
        "或用「智能工坊」处理格式类问题——那是您在界面里操作，不是我在聊天里直接改文件。\n\n"
        "如果您要改的是 Mod 逻辑/代码本身，请用您自己的编辑器；Remis 不是通用的 Mod 代码编辑器。"
    )
