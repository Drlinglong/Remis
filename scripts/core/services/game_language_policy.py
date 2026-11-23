"""Per-game target-language policy derived from the shared game catalog."""
from __future__ import annotations

from scripts.app_settings import GAME_ID_ALIASES, GAME_PROFILES, GAME_PROFILES_BY_ID, LANGUAGES


def supported_language_codes(game_id: str) -> list[str]:
    """Return canonical target codes allowed by a game's configured profile."""
    normalized = GAME_ID_ALIASES.get(str(game_id).casefold(), game_id)
    profile = GAME_PROFILES_BY_ID.get(normalized) or GAME_PROFILES.get(str(normalized))
    if profile is None:
        profile = next((item for item in GAME_PROFILES.values() if item.get("id") == normalized), None)
    if profile is None:
        return []
    return [LANGUAGES[key]["code"] for key in profile.get("supported_language_keys", [])
            if key in LANGUAGES]


def validate_target_language_codes(game_id: str, target_codes: list[str]) -> None:
    """Reject out-of-catalog Mars targets while leaving other games unchanged."""
    normalized = GAME_ID_ALIASES.get(str(game_id).casefold(), game_id)
    profile = GAME_PROFILES_BY_ID.get(normalized) or GAME_PROFILES.get(str(normalized))
    if profile and profile.get("id") == "surviving_mars":
        normalized = "surviving_mars"
    if normalized != "surviving_mars":
        return
    allowed = set(supported_language_codes(normalized))
    unsupported = sorted({str(code) for code in target_codes} - allowed)
    if unsupported:
        raise ValueError(
            "Unsupported Surviving Mars target language(s): " + ", ".join(unsupported)
            + ". Supported: " + ", ".join(supported_language_codes(normalized))
        )


def incremental_target_languages(game_profile, codes, custom_config):
    from scripts.app_settings import LANGUAGE_BY_CODE
    from scripts.core.services.game_support_service import get_game_support
    from scripts.schemas.agent_language import validate_shell_targets

    target_codes = [code.value for code in codes]
    shell = validate_shell_targets(target_codes, custom_config)
    if shell is not None:
        if not get_game_support(game_profile["id"])["shell_languages_supported"]:
            raise ValueError("This game does not support Paradox shell languages")
        return [shell]
    return [LANGUAGE_BY_CODE[code] for code in target_codes if code in LANGUAGE_BY_CODE]
