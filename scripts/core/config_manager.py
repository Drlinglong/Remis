import os
import json
import logging
from typing import Dict, Any, Set
from scripts.config import prompts

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages loading and providing access to externalized configurations.
    """
    
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self._game_profiles = None
        self._api_providers = None

    @property
    def game_profiles(self) -> Dict[str, Any]:
        """Lazy load game profiles."""
        if self._game_profiles is None:
            self.load_game_profiles()
        return self._game_profiles

    def load_game_profiles(self) -> None:
        """Loads game profiles from JSON and hydrates them with Python objects."""
        path = os.path.join(self.config_dir, "game_profiles.json")
        try:
            if not os.path.exists(path):
                logger.warning(f"Game profiles config not found at {path}")
                self._game_profiles = {}
                return

            with open(path, 'r', encoding='utf-8') as f:
                raw_profiles = json.load(f)

            hydrated_profiles = {}
            for key, profile in raw_profiles.items():
                hydrated = profile.copy()
                
                # Hydrate Sets
                if "protected_items" in hydrated:
                    hydrated["protected_items"] = set(hydrated["protected_items"])
                
                # Hydrate Prompts
                preset = hydrated.get("prompt_preset")
                if preset:
                    hydrated["prompt_template"] = getattr(prompts, f"{preset}_PROMPT_TEMPLATE", prompts.VICTORIA3_PROMPT_TEMPLATE)
                    hydrated["single_prompt_template"] = getattr(prompts, f"{preset}_SINGLE_PROMPT_TEMPLATE", prompts.VICTORIA3_SINGLE_PROMPT_TEMPLATE)
                    hydrated["format_prompt"] = getattr(prompts, f"{preset}_FORMAT_PROMPT", prompts.VICTORIA3_FORMAT_PROMPT)
                
                # Handle Metadata File Path (if nested)
                # JSON stores "dir/file.json", we need os.path.join logic?
                # Actually, os.path.join works fine with forward slashes on Windows usually, 
                # but if we want to be strict, we can normalize.
                # The existing code used os.path.join(".metadata", "metadata.json") which produces different separators on OS.
                # The JSON has ".metadata/metadata.json".
                if "metadata_file" in hydrated:
                    hydrated["metadata_file"] = os.path.normpath(hydrated["metadata_file"])

                hydrated_profiles[key] = hydrated

            self._game_profiles = hydrated_profiles
            logger.info(f"Loaded {len(hydrated_profiles)} game profiles from {path}")

        except Exception as e:
            logger.error(f"Failed to load game profiles: {e}")
            raise

    @property
    def api_providers(self) -> Dict[str, Any]:
        """Lazy load api providers."""
        if self._api_providers is None:
            self.load_api_providers()
        return self._api_providers

    def load_api_providers(self) -> None:
        """Loads API providers from JSON."""
        path = os.path.join(self.config_dir, "api_providers.json")
        try:
            if not os.path.exists(path):
                logger.warning(f"API providers config not found at {path}")
                self._api_providers = {}
                return

            with open(path, 'r', encoding='utf-8') as f:
                self._api_providers = json.load(f)
            logger.info(f"Loaded {len(self._api_providers)} API providers from {path}")

        except Exception as e:
            logger.error(f"Failed to load API providers: {e}")
    @property
    def user_config_path(self) -> str:
        return os.path.join(self.config_dir, "config.json")

    def _load_user_config(self) -> Dict[str, Any]:
        """Loads the generic user configuration."""
        try:
            if not os.path.exists(self.user_config_path):
                return {}
            with open(self.user_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load user config: {e}")
            return {}

    def _save_user_config(self, config: Dict[str, Any]) -> None:
        """Saves the generic user configuration."""
        try:
            with open(self.user_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save user config: {e}")

    def get_value(self, key: str, default: Any = None) -> Any:
        """Retrieves a value from the user configuration."""
        config = self._load_user_config()
        return config.get(key, default)

    def set_value(self, key: str, value: Any) -> None:
        """Sets a value in the user configuration and persists it."""
        config = self._load_user_config()
        config[key] = value
        self._save_user_config(config)

# Singleton instance
# Assuming DATA_DIR/config is the location
# We need to import paths from app_settings, but app_settings imports US?
# Circular dependency risk if we put the singleton instantiation here AND import it in app_settings.
# Ideally, app_settings defines paths, and we import paths here.
# But app_settings wants to use ConfigManager to EXPOSE game_profiles.

# Solution:
# 1. ConfigManager doesn't import app_settings. It takes paths in __init__.
# 2. app_settings imports ConfigManager class.
# 3. app_settings instantiates ConfigManager(DATA_DIR/config).
# 4. app_settings.GAME_PROFILES = config_manager.game_profiles
