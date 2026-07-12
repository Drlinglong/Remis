"""Lightweight help pack for Help Copilot (keyword routing, not vector RAG)."""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from typing import Literal

from scripts.app_settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

GroundingLevel = Literal["strong", "weak", "none", "policy"]

# Curated user-facing docs only (see docs/zh/copilot/rag-corpus-boundary.md).
HELP_DOCS: list[dict[str, object]] = [
    {
        "path": "zh/user-guides/getting-started.md",
        "title": "从零开始",
        "keywords": (
            "开始", "入门", "第一次", "新建", "创建项目", "怎么用", "从零",
            "新手", "流程", "getting started", "create project", "初次汉化",
        ),
        "max_chars": 4500,
    },
    {
        "path": "zh/user-guides/provider-setup-index.md",
        "title": "Provider 配置速查",
        "keywords": (
            "api", "key", "provider", "模型", "服务商", "lm studio", "ollama",
            "设置", "密钥", "连接", "base url", "接口",
        ),
        "max_chars": 3500,
    },
    {
        "path": "zh/user-guides/one-click-deploy.md",
        "title": "一键部署",
        "keywords": ("部署", "一键", "进游戏", "launcher", "启动器", "deploy", "安装"),
        "max_chars": 3000,
    },
    {
        "path": "zh/user-guides/fake-localization.md",
        "title": "假本地化",
        "keywords": ("假本地化", "假中文", "fake", "清理", "创意工坊", "workshop"),
        "max_chars": 3000,
    },
    {
        "path": "zh/user-guides/incremental-update.md",
        "title": "增量翻译",
        "keywords": ("增量", "更新", "原mod更新", "新增", "incremental"),
        "max_chars": 3000,
    },
    {
        "path": "zh/user-guides/proofreading.md",
        "title": "校对",
        "keywords": ("校对", "手改", "proofread", "改译文"),
        "max_chars": 2500,
    },
    {
        "path": "zh/user-guides/agent-workshop.md",
        "title": "智能工坊",
        "keywords": ("工坊", "格式", "修复", "变量", "标签", "workshop", "agent"),
        "max_chars": 2500,
    },
    {
        "path": "zh/user-guides/glossary.md",
        "title": "词典与词汇表",
        "keywords": ("词典", "词汇表", "术语", "glossary", "专有名词"),
        "max_chars": 2500,
    },
    {
        "path": "zh/user-guides/logs-and-diagnostics.md",
        "title": "日志与诊断",
        "keywords": ("日志", "报错", "闪退", "失败", "诊断", "log", "error"),
        "max_chars": 2500,
    },
    {
        "path": "zh/user-guides/error-catalog.md",
        "title": "错误目录",
        "keywords": ("错误", "失败", "timeout", "连接失败", "error"),
        "max_chars": 2500,
    },
]

AGENT_OPS_SUMMARY = """
## 你是谁
你是 Remis 产品副驾驶（Help Copilot）。用户使用的是打包好的 Remis 客户端，不是源码仓库。

## 绝对禁止 / 能力边界（优先于一切“帮忙”请求）
- **没有权限**直接读写用户磁盘上的 Mod 文件；用户说「帮我改一份 mod 文件」时必须明确拒绝，不能假装能改
- 不要修改或建议用户修改 Remis 源代码；不能改客户端程序
- 不要声称已经改好了客户端、已经改好了文件或已经删除了文件
- 不要要求用户把完整 API Key 粘贴到聊天里
- 不要发明白名单以外的 action
- 写操作（部署、清理假本地化、翻译落盘）在 Phase 1 只可文字说明，不可在聊天中直接执行
- **禁止在文档未覆盖时用「通常 / 一般 / 应该是 / 根据逻辑推断」编造功能说明**
- 能力边界问题（能不能改文件、有没有权限）依据本说明书回答，**不要**套「文档未覆盖」话术

## 遇到要改软件本身时
引导用户到 GitHub：
- Issues: https://github.com/Drlinglong/Remis/issues
- Copilot 讨论: https://github.com/Drlinglong/Remis/issues/132

## Phase 1 可提议的 action（仅这些）
- open_api_settings
- open_log_folder
- open_github_issues
- open_github_issue_132
- open_project_management
- open_create_project
- open_initial_translation
- open_proofreading
- open_agent_workshop
- open_glossary_manager
- open_provider_docs
- open_deploy_dialog  （仅导航到项目管理；真正部署需用户在 UI 确认）

## 首次汉化正确顺序
1. 设置 API（可选但强烈建议）
2. 项目管理 → 创建新项目
3. 初次翻译 → 选项目
4. 一键部署（必要时删除假本地化）
5. 校对 / 智能工坊 / 词典（可选）

不要让用户一上来就只点「初次翻译」却没有任何项目。
""".strip()


def _docs_root() -> str:
    return os.path.join(PROJECT_ROOT, "docs")


@lru_cache(maxsize=32)
def _read_doc_excerpt(rel_path: str, max_chars: int) -> str:
    full = os.path.abspath(os.path.join(_docs_root(), rel_path.replace("/", os.sep)))
    docs_root = os.path.abspath(_docs_root())
    if not full.startswith(docs_root) or not os.path.isfile(full):
        return ""
    try:
        with open(full, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        logger.warning("Failed to read help doc %s: %s", rel_path, exc)
        return ""

    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = text.strip()
    if len(text) > max_chars:
        text = text[: max_chars - 20].rstrip() + "\n\n…(截断)"
    return text


def score_query_against_docs(user_query: str) -> list[tuple[int, dict[str, object]]]:
    query = (user_query or "").lower()
    scored: list[tuple[int, dict[str, object]]] = []
    for doc in HELP_DOCS:
        score = 0
        for kw in doc["keywords"]:  # type: ignore[index]
            kw_s = str(kw).lower()
            if kw_s and kw_s in query:
                # Longer multi-char keywords weigh more.
                score += 3 if len(kw_s) >= 4 else 2 if len(kw_s) >= 2 else 1
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: (-x[0], str(x[1]["path"])))
    return scored


def grounding_level_from_score(best_score: int) -> GroundingLevel:
    if best_score >= 4:
        return "strong"
    if best_score >= 2:
        return "weak"
    return "none"


def select_help_excerpts(
    user_query: str,
    max_docs: int = 3,
) -> tuple[list[dict[str, str]], GroundingLevel, int]:
    """
    Return (excerpts, grounding_level, best_score).

    Important: do **not** force-inject getting-started for unrelated questions.
    Unmatched queries get empty excerpts + grounding none.
    """
    scored = score_query_against_docs(user_query)
    best_score = scored[0][0] if scored else 0
    level = grounding_level_from_score(best_score)

    if level == "none":
        return [], "none", 0

    # Weak: at most 1 doc; strong: up to max_docs.
    take = 1 if level == "weak" else max_docs
    selected = [item[1] for item in scored[:take]]

    excerpts: list[dict[str, str]] = []
    for doc in selected:
        body = _read_doc_excerpt(str(doc["path"]), int(doc["max_chars"]))
        if not body:
            continue
        excerpts.append(
            {
                "title": str(doc["title"]),
                "path": str(doc["path"]),
                "content": body,
            }
        )

    if not excerpts:
        return [], "none", best_score
    return excerpts, level, best_score


def build_system_prompt(
    user_query: str,
    locale: str = "zh",
) -> tuple[str, list[dict[str, str]], GroundingLevel, int]:
    excerpts, grounding, best_score = select_help_excerpts(user_query)
    sources = [{"title": e["title"], "path": e["path"]} for e in excerpts]

    if grounding == "none":
        docs_section = (
            "（无匹配的用户文档片段）\n"
            "当前问题在已收录的用户指南中没有可靠说明。"
        )
        grounding_rules = """
## 文档 grounding 状态：NONE（强制）
- 你 **没有** 可用的产品文档依据
- `confidence` **必须** 是 `"low"`
- `sources` **必须** 是空数组 `[]`
- **禁止** 猜测功能含义、菜单职责、实现细节（包括「通常是…」「根据项目管理逻辑…」）
- reply 必须明确告诉用户：当前用户文档未覆盖该问题；可建议到界面自行查看，或用 open_github_issues 反馈文档缺失
- suggested_actions 仅在确实有用时使用（例如 open_github_issues）；不要乱跳无关页面
""".strip()
    elif grounding == "weak":
        doc_blocks = [f"### {e['title']} ({e['path']})\n{e['content']}" for e in excerpts]
        docs_section = "\n\n".join(doc_blocks)
        grounding_rules = """
## 文档 grounding 状态：WEAK（强制）
- 文档匹配较弱；只允许复述下方片段里 **明确写到** 的内容
- 若用户问的点片段里没有写到：必须承认未写到，`confidence` 用 `"low"`，不要脑补
- 不要把「相关页面存在」说成「文档已说明该功能」
""".strip()
    else:
        doc_blocks = [f"### {e['title']} ({e['path']})\n{e['content']}" for e in excerpts]
        docs_section = "\n\n".join(doc_blocks)
        grounding_rules = """
## 文档 grounding 状态：STRONG
- 优先依据下方文档回答
- 文档未写到的细节仍应说不确定，并将 confidence 降为 low/medium
""".strip()

    system = f"""你是 Remis（Paradox Mod 本地化工厂）的产品帮助助手。
用通俗中文回答（若用户用英文提问可用英文）。面向新手，少用内部模块名。

{AGENT_OPS_SUMMARY}

{grounding_rules}

## 参考文档片段（只能依据这些内容；没有写到的不要编）
{docs_section}

## 输出格式（必须）
只输出一个 JSON 对象，不要 Markdown 代码围栏，不要额外前后缀。结构：
{{
  "reply": "给用户看的 Markdown 说明",
  "suggested_actions": [
    {{"action": "open_project_management", "label": "打开项目管理"}}
  ],
  "sources": [
    {{"title": "从零开始", "path": "zh/user-guides/getting-started.md"}}
  ],
  "confidence": "low|medium|high"
}}

规则：
- suggested_actions 只能使用上文列出的 action id；不确定就用空数组
- sources 只能引用上方真实出现的 path；grounding=none 时必须为空
- reply 中不要假装已经执行了操作；应说「您可以点击下方按钮…」
- 若问题与改软件/源码相关，引导 GitHub 并可用 open_github_issues
- 用户问第一次怎么汉化时，优先建议 open_create_project / open_project_management，而不是直接只开翻译页
- confidence=high 仅当文档明确覆盖用户问题时才允许
""".strip()

    _ = locale
    return system, sources, grounding, best_score
