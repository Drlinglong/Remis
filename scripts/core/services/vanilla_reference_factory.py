"""Construction policies for strict and fail-open vanilla reference reuse."""

import logging
from typing import Optional

from scripts.core.services.vanilla_reference_service import (
    VanillaReferenceResolver,
    VanillaReferenceService,
)


logger = logging.getLogger(__name__)


def create_reference_resolver_strict(
    reference_config: Optional[dict],
    *,
    game_profile: dict,
    source_lang: dict,
    target_lang: dict,
) -> Optional[VanillaReferenceResolver]:
    """Open a resolver while surfacing invalid paths and index failures."""

    config = reference_config or {}
    if not config.get("enabled", True) or not config.get("localization_path"):
        return None
    return VanillaReferenceService().open_resolver(
        game_id=game_profile.get("id", ""),
        localization_root=config["localization_path"],
        source_lang_code=source_lang.get("code", ""),
        target_lang_code=target_lang.get("code", ""),
        supported_language_keys=game_profile.get("supported_language_keys"),
        excluded_entries=config.get("excluded_entries"),
        encoding=game_profile.get("encoding", "utf-8-sig"),
    )


def create_reference_resolver(
    reference_config: Optional[dict],
    *,
    game_profile: dict,
    source_lang: dict,
    target_lang: dict,
) -> Optional[VanillaReferenceResolver]:
    """Return a resolver when configured; otherwise preserve the model workflow."""

    try:
        return create_reference_resolver_strict(
            reference_config,
            game_profile=game_profile,
            source_lang=source_lang,
            target_lang=target_lang,
        )
    except Exception as exc:
        logger.warning("Vanilla reference reuse is unavailable; using model translation: %s", exc)
        return None
