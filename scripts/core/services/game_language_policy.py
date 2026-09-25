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
