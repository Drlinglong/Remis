"""Validated shell-language parameters for external Agent plans."""

from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from scripts.schemas.translation import CustomLangConfig


class AgentCustomLangConfig(CustomLangConfig):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    code: Literal["custom"] = "custom"
    key: str
    folder_prefix: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,38}-$")

    @field_validator("key")
    @classmethod
    def require_game_language_shell(cls, value):
        from scripts.app_settings import LANGUAGE_BY_PARA_KEY

        if value not in LANGUAGE_BY_PARA_KEY:
            raise ValueError("Select a supported Paradox language key for the shell")
        return value


def validate_shell_targets(targets, config):
    has_custom = "custom" in targets
    if bool(config) != has_custom or (has_custom and targets != ["custom"]):
        raise ValueError("A shell plan requires only target 'custom' and custom_lang_config")
    return AgentCustomLangConfig.model_validate(config).model_dump() if config else None


def language_plan_details(args):
    """Expose approval-relevant identity without provider credentials."""
    return {
        "target_lang_codes": args.get("target_lang_codes", []),
        "custom_lang_config": args.get("custom_lang_config"),
        "api_provider": args.get("api_provider"),
        "model": args.get("model"),
    }
