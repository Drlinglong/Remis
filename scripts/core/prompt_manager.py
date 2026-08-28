import logging
from scripts.app_settings import GAME_PROFILES, GAME_PROFILES_BY_ID, config_manager

logger = logging.getLogger(__name__)


def _profile_and_storage_key(game_id: str):
    """Resolve either the persisted numeric key or the canonical game id."""
    if game_id in GAME_PROFILES:
        return GAME_PROFILES[game_id], game_id

    profile = GAME_PROFILES_BY_ID.get(game_id)
    if profile is None:
        return None, None

    storage_key = next(
        (key for key, candidate in GAME_PROFILES.items() if candidate is profile),
        game_id,
    )
    return profile, storage_key


def _get_override(overrides, game_id: str, storage_key: str):
    """Read new canonical-id overrides while retaining legacy numeric ones."""
    if game_id in overrides:
        return overrides[game_id]
    if storage_key in overrides:
        return overrides[storage_key]
    return None


class PromptManager:
    """
    Manages system prompts and custom prompts.
    Handles retrieval (merging defaults with overrides) and saving.
    """

    @staticmethod
    def get_all_prompts():
        """
        Returns a dictionary containing prompt info for all games,
        plus the custom global prompt.
        """
        overrides = config_manager.get_value("prompt_overrides", {})
        format_overrides = config_manager.get_value("format_prompt_overrides", {})
        custom_global = config_manager.get_value("custom_global_prompt", "")
        
        system_prompts = {}
        for game_id, profile in GAME_PROFILES.items():
            default_prompt = profile.get("prompt_template", "")
            current_prompt = overrides.get(game_id, default_prompt)
            
            system_prompts[game_id] = {
                "name": profile["name"],
                "default": default_prompt,
                "current": current_prompt,
                "is_overridden": game_id in overrides,
                "format_default": profile.get("format_prompt", ""),
                "format_current": format_overrides.get(game_id, profile.get("format_prompt", "")),
                "is_format_overridden": game_id in format_overrides
            }
            
        return {
            "system_prompts": system_prompts,
            "custom_global_prompt": custom_global
        }

    @staticmethod
    def get_effective_prompt(game_id: str) -> str:
        """Returns the effective prompt for a game (override or default)."""
        overrides = config_manager.get_value("prompt_overrides", {})
        profile, storage_key = _profile_and_storage_key(game_id)
        override = _get_override(overrides, game_id, storage_key)
        if override is not None:
            return override
        return profile.get("prompt_template", "") if profile else ""

    @staticmethod
    def get_effective_format_prompt(game_id: str) -> str:
        """Returns the effective format prompt for a game (override or default)."""
        overrides = config_manager.get_value("format_prompt_overrides", {})
        profile, storage_key = _profile_and_storage_key(game_id)
        override = _get_override(overrides, game_id, storage_key)
        if override is not None:
            return override
        if not profile:
            return ""
        
        # If no profile-specific format prompt, check fallback? 
        # Actually base_handler defines fallback logic. 
        # Here we just return what's in profile or empty.
        return profile.get("format_prompt", "")

    @staticmethod
    def get_custom_global_prompt() -> str:
        return config_manager.get_value("custom_global_prompt", "")

    @staticmethod
    def save_system_prompt_override(game_id: str, new_prompt: str):
        """Saves an override for a system prompt."""
        if game_id not in GAME_PROFILES:
            raise ValueError(f"Invalid game_id: {game_id}")
            
        overrides = config_manager.get_value("prompt_overrides", {})
        overrides[game_id] = new_prompt
        config_manager.set_value("prompt_overrides", overrides)
        logger.info(f"Saved prompt override for {game_id}")

    @staticmethod
    def save_format_prompt_override(game_id: str, new_prompt: str):
        """Saves an override for a format prompt."""
        if game_id not in GAME_PROFILES:
            raise ValueError(f"Invalid game_id: {game_id}")
            
        overrides = config_manager.get_value("format_prompt_overrides", {})
        overrides[game_id] = new_prompt
        config_manager.set_value("format_prompt_overrides", overrides)
        logger.info(f"Saved format prompt override for {game_id}")

    @staticmethod
    def save_custom_global_prompt(new_prompt: str):
        """Saves the custom global prompt."""
        config_manager.set_value("custom_global_prompt", new_prompt)
        logger.info("Saved custom global prompt")

    @staticmethod
    def reset_prompts(game_id: str = None, reset_all: bool = False, reset_custom: bool = False, reset_format: bool = False):
        """Resets prompts to default."""
        if reset_custom:
            config_manager.set_value("custom_global_prompt", "")
            logger.info("Reset custom global prompt")
            
        if reset_all:
            config_manager.set_value("prompt_overrides", {})
            config_manager.set_value("format_prompt_overrides", {})
            logger.info("Reset all prompt overrides")
        elif game_id:
            overrides = config_manager.get_value("prompt_overrides", {})
            if game_id in overrides:
                del overrides[game_id]
                config_manager.set_value("prompt_overrides", overrides)
                logger.info(f"Reset prompt override for {game_id}")
            
            if reset_format:
                overrides = config_manager.get_value("format_prompt_overrides", {})
                if game_id in overrides:
                    del overrides[game_id]
                    config_manager.set_value("format_prompt_overrides", overrides)
                    logger.info(f"Reset format prompt override for {game_id}")

prompt_manager = PromptManager()
