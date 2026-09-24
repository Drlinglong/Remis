"""Explicit adapter registration, independent of providers and user state."""
from pathlib import Path

from .contracts import GameAdapter

ADAPTER_FACTORIES = {
    "project_zomboid": ("project_zomboid", "ProjectZomboidAdapter"),
    "rimworld": ("rimworld", "RimWorldAdapter"),
}


def resource_adapter(profile: dict | str | None) -> GameAdapter | None:
    """Return a structured resource adapter, preserving legacy workflow defaults."""
    game_id = profile if isinstance(profile, str) else (profile or {}).get("id", "")
    factory = ADAPTER_FACTORIES.get(game_id)
    if not factory:
        return None
    from importlib import import_module
    module, name = factory
    return getattr(import_module(f"{__package__}.{module}"), name)()


def get_adapter(profile: dict) -> GameAdapter:
    adapter = resource_adapter(profile)
    if adapter:
        return adapter
    from .legacy import LegacyAdapter
    return LegacyAdapter(profile)


def adapter_for_path(path: str | Path) -> GameAdapter | None:
    """Recognize only game resource directories; generic JSON remains interchange."""
    candidate = Path(path)
    parts = [part.casefold() for part in candidate.parts]
    suffix = candidate.suffix.casefold()
    if "translate" in parts and suffix in {".txt", ".json"}:
        return resource_adapter("project_zomboid")
    if suffix in {".xml", ".txt"}:
        if "languages" in parts and any(p in parts for p in ("keyed", "definjected", "strings")):
            return resource_adapter("rimworld")
        if "defs" in parts and suffix == ".xml":
            return resource_adapter("rimworld")
    return None


def game_capabilities(game_id: str) -> dict:
    structured = game_id in ADAPTER_FACTORIES
    csv = game_id == "surviving_mars"
    return {
        "resource_adapter": game_id if structured else ("surviving_mars_csv" if csv else "paradox"),
        "independent_translation_mod": structured,
        "paradox_deployment": not (structured or csv),
        "source_cleanup": not (structured or csv),
        "runtime_verified": False if structured else None,
        "coverage_kind": "recognized_resources" if structured else "localization_files",
    }
