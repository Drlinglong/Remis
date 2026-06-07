import logging
from dataclasses import dataclass
from typing import Optional, List

from scripts.core import api_handler
from scripts.app_settings import LANGUAGES
from scripts.utils import i18n
from scripts.utils.system_utils import slugify_to_ascii


@dataclass(frozen=True)
class InitialTranslationRunPlan:
    is_batch_mode: bool
    output_folder_name: str
    primary_target_lang: dict


def build_run_plan(mod_name: str, target_languages: List[dict]) -> InitialTranslationRunPlan:
    is_batch_mode = len(target_languages) > 1
    if is_batch_mode:
        return InitialTranslationRunPlan(
            is_batch_mode=True,
            output_folder_name=f"Multilanguage-{slugify_to_ascii(mod_name)}",
            primary_target_lang=LANGUAGES["1"],
        )

    target_lang = target_languages[0]
    prefix = target_lang.get("folder_prefix", f"{target_lang['code']}-")
    return InitialTranslationRunPlan(
        is_batch_mode=False,
        output_folder_name=f"{prefix}{slugify_to_ascii(mod_name)}",
        primary_target_lang=target_lang,
    )


def resolve_provider_model(selected_provider: str, model_name: Optional[str]) -> Optional[str]:
    if selected_provider == "gemini_cli" and not model_name:
        logging.warning("No model specified for Gemini CLI. Defaulting to 'gemini-1.5-flash'.")
        return "gemini-1.5-flash"
    return model_name


def create_translation_handler(selected_provider: str, model_name: Optional[str]):
    handler = api_handler.get_handler(selected_provider, model_name=model_name)
    if not handler or not handler.client:
        logging.warning(i18n.t("api_key_not_configured", provider=selected_provider))
        return None
    return handler
