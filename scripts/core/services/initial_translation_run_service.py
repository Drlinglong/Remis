import logging
from dataclasses import dataclass
from typing import Optional, List

from scripts.app_settings import LANGUAGES
from scripts.core import api_handler
from scripts.utils import i18n
from scripts.core.services.provider_runtime import handler_for_selection
from scripts.core.services.translation_task_runtime import get_output_folder_names


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


def resolve_provider_model(selected_provider: str, model_name: Optional[str]) -> Optional[str]:
    return model_name


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
