"""Trust-boundary helpers for user-selected official localization roots."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from scripts.app_settings import GAME_PROFILES, VANILLA_REFERENCE_DB_PATH
from scripts.core.services.paradox_installation_discovery import discover_paradox_localizations


def trusted_reference_candidates(
    db_path: Path,
    explicit: Iterable[str | Path] | None = None,
) -> tuple[Path, ...]:
    """Return an exact allowlist of official roots accepted by the indexer."""

    if explicit is not None:
        candidates = tuple(Path(root) for root in explicit)
    elif db_path != Path(VANILLA_REFERENCE_DB_PATH):
        candidates = (db_path.parent, *db_path.parent.rglob("*"))
    else:
        installations = discover_paradox_localizations(GAME_PROFILES)
        candidates = tuple(
            Path(path)
            for item in installations
            for path in (item["localization_path"], *item["localization_paths"])
        )
    unique = {
        os.path.normcase(os.path.realpath(os.fspath(path))): Path(path)
        for path in candidates
        if path.is_dir()
    }
    return tuple(unique.values())
