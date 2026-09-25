import logging
from dataclasses import dataclass
from typing import Optional, List

from scripts.app_settings import LANGUAGES
from scripts.core import api_handler
from scripts.utils import i18n
from scripts.core.services.provider_runtime import handler_for_selection
from scripts.core.services.translation_task_runtime import get_output_folder_names
from scripts.utils.system_utils import slugify_to_ascii


@dataclass(frozen=True)
class InitialTranslationRunPlan:
    is_batch_mode: bool
    output_folder_name: str
    primary_target_lang: dict


def build_run_plan(
    mod_name: str,
    target_languages: List[dict],
    project_id: Optional[str] = None,
    output_folder_name: Optional[str] = None,
) -> InitialTranslationRunPlan:
    resolved_folder_name = output_folder_name or get_output_folder_names(
        mod_name,
        target_languages,
        project_id,
    )[0]
    is_batch_mode = len(target_languages) > 1
    if is_batch_mode:
        return InitialTranslationRunPlan(
            is_batch_mode=True,
            output_folder_name=resolved_folder_name,
            primary_target_lang=LANGUAGES["1"],
        )

    target_lang = target_languages[0]
    return InitialTranslationRunPlan(
        is_batch_mode=False,
        output_folder_name=resolved_folder_name,
        primary_target_lang=target_lang,
    )


def language_output_folder_name(mod_name: str, target_lang: dict) -> str:
    """Return the same stable language-prefixed folder used by single-target runs."""
    prefix = target_lang.get("folder_prefix", f"{target_lang['code']}-")
    return f"{prefix}{slugify_to_ascii(mod_name)}"


def resolve_provider_model(selected_provider: str, model_name: Optional[str]) -> Optional[str]:
    return model_name


def resource_output_folder(base_name: str, game_profile: dict, run_id: str) -> str:
    """Keep each resource package run separate while retaining its resume identity."""
    from scripts.core.game_adapters.registry import resource_adapter
    if not resource_adapter(game_profile):
        return base_name
    import hashlib
    return f"{base_name}-{hashlib.sha256(str(run_id).encode('utf-8')).hexdigest()[:12]}"


def create_translation_handler(
    selected_provider: str,
    model_name: Optional[str],
    provider_runtime=None,
):
    handler = (
        handler_for_selection(selected_provider, model_name, provider_runtime)
        if provider_runtime is not None
        else api_handler.get_handler(selected_provider, model_name=model_name)
    )
    if not handler or not handler.client:
        logging.warning(i18n.t("api_key_not_configured", provider=selected_provider))
        return None
    return handler
