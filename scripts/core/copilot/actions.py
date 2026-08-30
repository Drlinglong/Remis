"""Server-owned action registry for Help Copilot and approved workflows."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from scripts.core.copilot.workflow_entities import canonicalize_workflow_entities


class _NoActionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ProjectNavigationArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str | None = None
    task_id: str | None = None


class LocalizationWorkflowArgs(BaseModel):
    """Complete conversation-derived inputs for opening the approval workflow."""

    model_config = ConfigDict(extra="forbid")
    project_mode: Literal["existing", "new"]
    project_id: str | None = None
    folder_path: str | None = None
    project_name: str | None = None
    game_id: str | None = None
    source_language: str | None = None
    target_languages: list[str] = Field(min_length=1)
    api_provider: str
    model: str

    @model_validator(mode="after")
    def validate_project_reference(self) -> "LocalizationWorkflowArgs":
        if not _nonempty(self.api_provider) or not _nonempty(self.model):
            raise ValueError("Provider and model are required")
        if self.project_mode == "existing":
            if not _nonempty(self.project_id) and not _nonempty(self.project_name):
                raise ValueError("An existing project requires project_id or project_name")
            return self
        required = (
            self.folder_path,
            self.project_name,
            self.game_id,
            self.source_language,
        )
        if not all(_nonempty(value) for value in required):
            raise ValueError("A new project requires path, name, game, and source language")
        return self


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _workflow_args(
    raw_args: dict[str, Any],
    defaults: dict[str, str] | None,
    entity_catalog: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Validate a complete workflow handoff; incomplete model proposals fail closed."""
    candidate = dict(raw_args)
    legacy_target = candidate.pop("target_language", None)
    if "target_languages" not in candidate and _nonempty(legacy_target):
        candidate["target_languages"] = [legacy_target.strip()]
    for field in ("api_provider", "model"):
        if not _nonempty(candidate.get(field)) and defaults:
            candidate[field] = defaults.get(field)
    candidate = canonicalize_workflow_entities(candidate, entity_catalog)
    if candidate is None:
        return None
    try:
        parsed = LocalizationWorkflowArgs.model_validate(candidate)
    except ValidationError:
        return None
    args = parsed.model_dump(exclude_none=True)
    args["target_languages"] = list(dict.fromkeys(
        value.strip() for value in args["target_languages"] if _nonempty(value)
    ))
    if not args["target_languages"]:
        return None
    return args


ACTION_ARG_MODELS: dict[str, type[BaseModel]] = {
    "start_localization_workflow": LocalizationWorkflowArgs,
    "open_initial_translation": _ProjectNavigationArgs,
    "open_proofreading": _ProjectNavigationArgs,
    "open_agent_workshop": _ProjectNavigationArgs,
    "open_deploy_dialog": _ProjectNavigationArgs,
}

# Models may choose an action ID and validated args only. Labels, risk, and
# confirmation requirements are server-owned and never copied from model output.
ACTION_REGISTRY: dict[str, dict[str, Any]] = {
    "none": {
        "label": "无需操作",
        "description": "仅文字回答，不触发客户端动作",
        "risk": "read_only",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "none",
    },
    "open_api_settings": {
        "label": "打开 API 设置",
        "description": "跳转到设置页的 API 配置",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/settings",
        "hash_hint": "api",
    },
    "open_log_folder": {
        "label": "打开日志文件夹",
        "description": "在资源管理器中打开 Remis 日志目录",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "api_post",
        "endpoint": "/api/system/open-logs",
    },
    "open_github_issues": {
        "label": "打开 GitHub Issues",
        "description": "在浏览器打开问题反馈页",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "open_url",
        "url": "https://github.com/Drlinglong/Remis/issues",
    },
    "open_github_issue_132": {
        "label": "查看 Copilot 讨论 (#132)",
        "description": "打开 #132 功能讨论",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "open_url",
        "url": "https://github.com/Drlinglong/Remis/issues/132",
    },
    "open_project_management": {
        "label": "打开项目管理",
        "description": "跳转到项目管理页",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/project-management",
    },
    "open_create_project": {
        "label": "去创建新项目",
        "description": "打开项目管理（创建入口）",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/project-management",
    },
    "start_localization_workflow": {
        "label": "帮我规划并开始汉化",
        "description": "在对话中确认 Mod、语言和技术参数，生成待批准的完整汉化计划",
        "risk": "read_only_until_approval",
        "requires_confirmation": False,
        "phase": 2,
        "client_kind": "workflow",
        "workflow": "localize_mod_v1",
    },
    "open_initial_translation": {
        "label": "打开初次翻译",
        "description": "跳转到初次翻译页",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/translation",
    },
    "open_proofreading": {
        "label": "打开校对",
        "description": "跳转到校对页",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/proofreading",
    },
    "open_agent_workshop": {
        "label": "打开智能工坊",
        "description": "跳转到智能工坊页",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/agent-workshop",
    },
    "open_glossary_manager": {
        "label": "打开词汇表管理",
        "description": "跳转到词汇表管理页",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/glossary-manager",
    },
    "open_provider_docs": {
        "label": "打开 Provider 设置说明",
        "description": "引导到设置页配置服务商",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/settings",
    },
    "open_deploy_dialog": {
        "label": "打开项目管理（部署入口）",
        "description": "部署对话框在项目上下文中；先打开项目管理",
        "risk": "safe_ui_navigation",
        "requires_confirmation": False,
        "phase": 1,
        "client_kind": "navigate",
        "path": "/project-management",
    },
}


def list_actions(phase: int | None = 1) -> list[dict[str, Any]]:
    items = []
    for action_id, meta in ACTION_REGISTRY.items():
        if phase is not None and meta.get("phase", 1) > phase:
            continue
        if action_id == "none":
            continue
        items.append(
            {
                "action": action_id,
                "label": meta["label"],
                "description": meta["description"],
                "risk": meta["risk"],
                "requires_confirmation": bool(meta.get("requires_confirmation", False)),
                "phase": meta.get("phase", 1),
            }
        )
    return items


def filter_suggested_actions(
    raw_actions: list[Any] | None,
    *,
    workflow_defaults: dict[str, str] | None = None,
    workflow_entity_catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Keep only whitelist actions; drop unknown / none."""
    if not raw_actions:
        return []

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_actions:
        if not isinstance(item, dict):
            continue
        action_id = str(item.get("action") or "").strip()
        if not action_id or action_id == "none":
            continue
        if action_id not in ACTION_REGISTRY:
            continue
        if action_id in seen:
            continue

        meta = ACTION_REGISTRY[action_id]
        raw_args = item.get("args") if isinstance(item.get("args"), dict) else {}
        if action_id == "start_localization_workflow":
            args = _workflow_args(raw_args, workflow_defaults, workflow_entity_catalog)
            if args is None:
                continue
            seen.add(action_id)
            cleaned.append(
                {
                    "action": action_id,
                    "label": meta["label"],
                    "args": args,
                    "requires_confirmation": bool(meta.get("requires_confirmation", False)),
                    "risk": meta.get("risk", "safe_ui_navigation"),
                }
            )
            if len(cleaned) >= 4:
                break
            continue
        args_model = ACTION_ARG_MODELS.get(action_id, _NoActionArgs)
        try:
            args = args_model.model_validate(raw_args).model_dump(exclude_none=True)
        except ValidationError:
            args = {}
        seen.add(action_id)
        cleaned.append(
            {
                "action": action_id,
                "label": meta["label"],
                "args": args,
                "requires_confirmation": bool(meta.get("requires_confirmation", False)),
                "risk": meta.get("risk", "safe_ui_navigation"),
            }
        )
        if len(cleaned) >= 4:
            break

    return cleaned


def get_client_handler(action_id: str) -> dict[str, Any] | None:
    meta = ACTION_REGISTRY.get(action_id)
    if not meta:
        return None
    return {
        "action": action_id,
        "client_kind": meta.get("client_kind"),
        "path": meta.get("path"),
        "endpoint": meta.get("endpoint"),
        "url": meta.get("url"),
        "hash_hint": meta.get("hash_hint"),
        "label": meta.get("label"),
        "workflow": meta.get("workflow"),
    }
