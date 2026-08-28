"""Maintenance workflow for persistent vanilla reference libraries."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from scripts.app_settings import GAME_PROFILES, GAME_PROFILES_BY_ID
from scripts.core.services.paradox_installation_discovery import discover_paradox_localizations
from scripts.core.services.vanilla_reference_service import VanillaReferenceService


class ReferenceLibraryService:
    def __init__(self, reference_service: VanillaReferenceService | None = None) -> None:
        self.reference_service = reference_service or VanillaReferenceService()

    def status(self) -> dict:
        active = {item.game_id: item for item in self.reference_service.list_active_indexes()}
        libraries = []
        for profile in GAME_PROFILES.values():
            game_id = profile["id"]
            info = active.get(game_id)
            libraries.append({
                "game_id": game_id,
                "game_name": profile.get("name", game_id),
                "available": info is not None,
                **(self._serialize_info(info) if info else {}),
            })
        return {"status": "success", "libraries": libraries}

    def discover(self) -> dict:
        return {
            "status": "success",
            "candidates": discover_paradox_localizations(GAME_PROFILES),
        }

    def build(self, game_id: str, localization_path: str) -> dict:
        profile = GAME_PROFILES_BY_ID.get(game_id)
        if profile is None:
            raise ValueError(f"Unsupported game: {game_id}")
        self._validate_profile_path(profile, localization_path)
        info = self.reference_service.build_index(
            game_id=game_id,
            localization_root=localization_path,
            supported_language_keys=profile.get("supported_language_keys"),
            encoding=profile.get("encoding", "utf-8-sig"),
        )
        return {
            "status": "success",
            "library": {
                "game_id": game_id,
                "game_name": profile.get("name", game_id),
                "available": True,
                **self._serialize_info(info),
            },
        }

    def discover_and_build(self) -> dict:
        candidates = discover_paradox_localizations(GAME_PROFILES)
        built = []
        errors = []
        for candidate in candidates:
            try:
                built.append(self.build(
                    candidate["game_id"],
                    candidate["localization_path"],
                )["library"])
            except (OSError, ValueError) as exc:
                errors.append({**candidate, "error": str(exc)})
        return {"status": "success", "candidates": candidates, "built": built, "errors": errors}

    def _validate_profile_path(self, profile: dict, localization_path: str) -> None:
        path = Path(localization_path).expanduser().resolve(strict=True)
        expected = profile.get("source_localization_folder", "localization").casefold()
        if path.name.casefold() != expected:
            raise ValueError(f"Expected the game's {expected} directory")
        if path.parent.name.casefold() != "game":
            raise ValueError("Reference path must be located directly under the game's game directory")

    def _serialize_info(self, info) -> dict:
        payload = asdict(info)
        payload["entry_count"] = self.reference_service.count_entries(info.reference_set_id)
        return payload
