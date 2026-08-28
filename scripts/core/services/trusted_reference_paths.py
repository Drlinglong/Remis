"""Trust-boundary helpers for user-selected official localization roots."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from scripts.app_settings import VANILLA_REFERENCE_DB_PATH
from scripts.core.services.paradox_installation_discovery import discover_steam_library_roots


def resolve_trusted_reference_root(
    value: str | Path,
    *,
    db_path: Path,
    trusted_roots: Iterable[str | Path] | None = None,
) -> Path:
    """Normalize a selected path and require containment in a trusted local root."""

    roots = tuple(trusted_roots) if trusted_roots is not None else tuple(
        library / "steamapps" / "common"
        for library in discover_steam_library_roots()
    )
    if trusted_roots is None and db_path != Path(VANILLA_REFERENCE_DB_PATH):
        roots = (db_path.parent, *roots)
    candidate = os.path.realpath(os.path.expanduser(os.fspath(value)))
    if not any(_is_within(candidate, os.path.realpath(os.fspath(root))) for root in roots):
        raise ValueError("Reference path must belong to a trusted Steam library")
    return Path(candidate)


def _is_within(candidate: str, trusted_root: str) -> bool:
    candidate_key = os.path.normcase(candidate)
    trusted_key = os.path.normcase(trusted_root)
    try:
        return os.path.commonpath((candidate_key, trusted_key)) == trusted_key
    except ValueError:
        return False
