"""Allowlisted, agent-selected help skills for Remis Help Copilot."""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Literal

from scripts.app_settings import RESOURCE_DIR

logger = logging.getLogger(__name__)

GroundingLevel = Literal["strong", "weak", "none", "policy"]
MAX_SELECTED_SKILLS = 3

# The model sees only this manifest. It chooses skill IDs, never filesystem paths.
HELP_SKILLS: dict[str, dict[str, Any]] = {
    "getting_started": {
        "title": "从零开始",
        "description": "第一次使用 Remis、创建项目、初次汉化和完整新手流程。",
        "resources": ("zh/user-guides/getting-started.md",),
    },
    "provider_setup": {
        "title": "Provider 配置总览",
        "description": "选择 Provider，理解 API Key、Base URL、模型和配置入口。",
        "resources": ("zh/user-guides/provider-setup-index.md",),
    },
    "ollama_setup": {
        "title": "Ollama 配置",
        "description": "安装、配置或排查 Ollama 本地模型服务。",
        "resources": ("zh/user-guides/using_ollama.md",),
    },
    "custom_openai_setup": {
        "title": "自定义 OpenAI API",
        "description": "配置 OpenAI-compatible Base URL、API Key 和自定义模型。",
        "resources": ("zh/user-guides/using_custom_openai_api.md",),
    },
    "modelscope_siliconflow_setup": {
        "title": "ModelScope 与 SiliconFlow",
        "description": "配置魔搭社区或硅基流动在线模型服务。",
        "resources": ("zh/user-guides/using_modelscope_and_siliconflow.md",),
    },
    "deployment": {
        "title": "一键部署",
        "description": "把翻译部署进游戏、启动器加载顺序和部署后的排查。",
        "resources": ("zh/user-guides/one-click-deploy.md",),
    },
    "fake_localization": {
        "title": "假本地化",
        "description": "假中文、假本地化冲突、创意工坊语言目录和安全清理。",
        "resources": ("zh/user-guides/fake-localization.md",),
    },
    "incremental_translation": {
        "title": "增量翻译",
        "description": "Mod 更新后只翻新增内容、归档基线和增量翻译流程。",
        "resources": ("zh/user-guides/incremental-update.md",),
    },
    "import_translation": {
        "title": "导入已有译文",
        "description": "导入半成品汉化或已有翻译，并接入 Remis 项目流程。",
        "resources": ("zh/user-guides/import-existing-translations.md",),
    },
    "proofreading": {
        "title": "校对",
        "description": "人工修改译文、保存条目、格式验证和校对工作区。",
        "resources": ("zh/user-guides/proofreading.md",),
    },
    "agent_workshop": {
        "title": "智能工坊",
        "description": "扫描和修复格式、变量、标签等批量问题。",
        "resources": ("zh/user-guides/agent-workshop.md",),
    },
    "glossary": {
        "title": "词典与词汇表",
        "description": "术语、专有名词、词典创建、绑定和使用。",
        "resources": ("zh/user-guides/glossary.md",),
    },
    "neologism_tribunal": {
        "title": "术语法庭",
        "description": "审议新词、术语候选和统一译名。",
        "resources": ("zh/user-guides/neologism-tribunal.md",),
    },
    "project_tracking": {
        "title": "项目追踪",
        "description": "查看项目状态、进度和后续任务。",
        "resources": ("zh/user-guides/project-tracking.md",),
    },
    "settings": {
        "title": "设置",
        "description": "Remis 设置页面、通用选项和配置说明。",
        "resources": ("zh/user-guides/settings.md",),
    },
    "thumbnail_generator": {
        "title": "缩略图生成器",
        "description": "使用工具生成 Mod 缩略图。",
        "resources": ("zh/user-guides/tools-thumbnail-generator.md",),
    },
    "faq": {
        "title": "常见问题",
        "description": "Remis 使用中的常见问题和简短答案。",
        "resources": ("zh/user-guides/faq.md",),
    },
    "factory_workflow": {
        "title": "汉化工厂如何工作",
        "description": "理解 Remis 的整体汉化流程和各阶段关系。",
        "resources": ("zh/user-guides/how_the_factory_works.md",),
    },
    "logs_and_errors": {
        "title": "日志与错误诊断",
        "description": "日志位置、闪退、连接失败、错误代码和故障反馈。",
        "resources": (
            "zh/user-guides/logs-and-diagnostics.md",
            "zh/user-guides/error-catalog.md",
        ),
    },
}


def validate_help_skill_manifest() -> list[str]:
    """Report packaged guide files that cannot be selected by the agent."""
    registered = {path for meta in HELP_SKILLS.values() for path in meta["resources"]}
    guide_root = os.path.join(_docs_root(), "zh", "user-guides")
    available = {
        f"zh/user-guides/{name}"
        for name in os.listdir(guide_root)
        if name.lower().endswith(".md")
    } if os.path.isdir(guide_root) else set()
    return sorted(available - registered)

AGENT_OPS_SUMMARY = """
## 你是谁
你是 Remis 产品副驾驶（Help Copilot）。用户使用的是打包好的 Remis 客户端，不是源码仓库。

## 绝对禁止 / 能力边界（优先于一切“帮忙”请求）
- **没有权限**直接读写用户磁盘上的 Mod 文件；用户说「帮我改一份 mod 文件」时必须明确拒绝，不能假装能改
- 不要修改或建议用户修改 Remis 源代码；不能改客户端程序
- 不要声称已经改好了客户端、已经改好了文件或已经删除了文件
- 不要要求用户把完整 API Key 粘贴到聊天里
- 不要发明白名单以外的 action
- 写操作（部署、清理假本地化、翻译落盘）不能由聊天直接执行；工作流必须先展示固定计划并由用户明确批准
- **禁止在文档未覆盖时用「通常 / 一般 / 应该是 / 根据逻辑推断」编造功能说明**
- 能力边界问题依据本说明书回答，不要套「文档未覆盖」话术

## 遇到要改软件本身时
引导用户到 GitHub：https://github.com/Drlinglong/Remis/issues

## 可提议的 action（仅这些）
- open_api_settings
- open_log_folder
- open_github_issues
- open_github_issue_132
- open_project_management
- open_create_project
- start_localization_workflow（在对话中确认路径、游戏、源语言和目标语言；批准前只读）
- open_initial_translation
- open_proofreading
- open_agent_workshop
- open_glossary_manager
- open_provider_docs
- open_deploy_dialog（仅导航；真正部署需用户在 UI 确认）

## 首次汉化正确顺序
1. 设置 API（可选但强烈建议）
2. 项目管理 → 创建新项目
3. 初次翻译 → 选项目
4. 一键部署（必要时删除假本地化）
5. 校对 / 智能工坊 / 词典（可选）

不要让用户一上来只点「初次翻译」却没有任何项目。
用户明确说想开始汉化一个 Mod 时，优先建议 start_localization_workflow，而不是只解释或只跳转页面。
先明确告诉用户：「我可以引导您在程序中逐步操作，也可以帮您规划并启动完整汉化流程。」
如果用户已经给出 Mod 路径、游戏、源语言或目标语言，把已知值放进 start_localization_workflow 的 args；不要让用户在割裂的弹窗里重复填写。
在执行任何写操作前，必须在对话内展示完整参数和风险，并由用户点击批准按钮。
""".strip()


def _docs_root() -> str:
    """Use bundled resources when frozen and the repository resources in development."""
    return os.path.abspath(os.path.join(RESOURCE_DIR, "docs"))


@lru_cache(maxsize=32)
def _read_allowlisted_doc(rel_path: str) -> str:
    full = os.path.abspath(os.path.join(_docs_root(), rel_path.replace("/", os.sep)))
    docs_root = _docs_root()
    try:
        inside_docs = os.path.commonpath((docs_root, full)) == docs_root
    except ValueError:
        inside_docs = False
    if not inside_docs or not os.path.isfile(full):
        logger.warning("Help skill resource is unavailable: %s", rel_path)
        return ""
    try:
        with open(full, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        logger.warning("Failed to read help skill resource %s: %s", rel_path, exc)
        return ""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def build_skill_router_prompt(history: list[dict[str, str]], locale: str = "zh") -> str:
    """Compatibility prompt for providers without native function calling."""
    catalog = [
        {"id": skill_id, "title": meta["title"], "description": meta["description"]}
        for skill_id, meta in HELP_SKILLS.items()
    ]
    return f"""你是 Remis Help Copilot 的技能路由 Agent。
根据最近对话判断回答当前用户问题需要读取哪些 Help Skill。
不要根据单个关键词机械匹配；追问必须结合前文理解。

可用工具：read_help_skill(skill_id)，读取随安装包发布的只读用户帮助技能。

Help Skills：
{json.dumps(catalog, ensure_ascii=False, indent=2)}

最近对话：
{json.dumps(history[-8:], ensure_ascii=False, indent=2)}

只输出 JSON，不要代码围栏：
{{"tool_calls":[{{"name":"read_help_skill","arguments":{{"skill_id":"provider_setup"}}}}]}}

规则：最多调用 {MAX_SELECTED_SKILLS} 个；只允许上面的 ID；无需文档时返回空数组；本轮不要回答用户。
当前界面语言：{locale}
""".strip()


def parse_skill_tool_calls(raw: str) -> list[str]:
    """Validate model-proposed tool calls and return unique allowlisted skill IDs."""
    if not raw:
        return []
    candidate = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", candidate, re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            payload = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return []
    if not isinstance(payload, dict) or not isinstance(payload.get("tool_calls"), list):
        return []

    selected: list[str] = []
    for call in payload["tool_calls"]:
        if not isinstance(call, dict) or call.get("name") != "read_help_skill":
            continue
        arguments = call.get("arguments")
        if not isinstance(arguments, dict):
            continue
        skill_id = str(arguments.get("skill_id") or "").strip()
        if skill_id not in HELP_SKILLS or skill_id in selected:
            continue
        selected.append(skill_id)
        if len(selected) >= MAX_SELECTED_SKILLS:
            break
    return selected


def read_help_skills(skill_ids: list[str]) -> list[dict[str, str]]:
    """Execute validated read_help_skill calls against bundled, allowlisted resources."""
    excerpts: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for skill_id in skill_ids[:MAX_SELECTED_SKILLS]:
        meta = HELP_SKILLS.get(skill_id)
        if not meta:
            continue
        for rel_path in meta["resources"]:
            if rel_path in seen_paths:
                continue
            seen_paths.add(rel_path)
            content = _read_allowlisted_doc(rel_path)
            if content:
                excerpts.append(
                    {
                        "skill_id": skill_id,
                        "title": str(meta["title"]),
                        "path": rel_path,
                        "content": content,
                    }
                )
    return excerpts


def build_system_prompt(
    selected_skill_ids: list[str],
    locale: str = "zh",
    page_context: dict | None = None,
) -> tuple[str, list[dict[str, str]], GroundingLevel, int]:
    excerpts = read_help_skills(selected_skill_ids)
    sources = [{"title": e["title"], "path": e["path"]} for e in excerpts]
    grounding: GroundingLevel = "strong" if excerpts else "none"
    score = 100 if excerpts else 0

    if excerpts:
        docs_section = "\n\n".join(
            f"### [{e['skill_id']}] {e['title']} ({e['path']})\n{e['content']}" for e in excerpts
        )
        grounding_rules = "只依据 Agent 主动读取的 Help Skill 回答；未写到的细节说明不确定。"
    else:
        docs_section = "（Agent 没有选择到可用 Help Skill，或安装资源缺失。）"
        grounding_rules = (
            "grounding=none：confidence 必须为 low，sources 必须为空；"
            "禁止猜测 Remis 功能，明确说明当前帮助技能未覆盖。"
        )

    page_context_section = json.dumps(page_context, ensure_ascii=False, indent=2) if page_context else "（未提供）"
    system = f"""你是 Remis（Paradox Mod 本地化工厂）的产品帮助助手。
用通俗中文回答（若用户用英文提问可用英文）。面向新手，少用内部模块名。

{AGENT_OPS_SUMMARY}

## 当前 Remis 页面上下文
这是 Remis 生成的只读状态快照。可以用它解释用户当前所在步骤和下一步，但不得声称已经替用户执行操作。
{page_context_section}

## Grounding 规则
{grounding_rules}

## read_help_skill 工具返回
{docs_section}

## 输出格式（必须）
只输出一个 JSON 对象，不要 Markdown 代码围栏：
{{
  "reply": "给用户看的 Markdown 说明",
  "suggested_actions": [{{"action": "start_localization_workflow", "args": {{"folder_path": "用户给出的路径", "game_id": "vic3", "source_language": "en", "target_language": "zh-CN"}}}}],
  "sources": [{{"title": "从零开始", "path": "zh/user-guides/getting-started.md"}}],
  "confidence": "low|medium|high"
}}

规则：suggested_actions 只能使用上面的 action id；sources 只能引用工具结果中的 path；不要假装已经执行操作。
当前界面语言：{locale}
""".strip()
    return system, sources, grounding, score
