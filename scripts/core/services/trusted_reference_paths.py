"""Trust-boundary helpers for user-selected official localization roots."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from scripts.app_settings import VANILLA_REFERENCE_DB_PATH
from scripts.core.services.paradox_installation_discovery import discover_steam_library_roots


def trusted_reference_roots(
    db_path: Path,
    trusted_roots: Iterable[str | Path] | None = None,
) -> tuple[str, ...]:
    """Return normalized Steam roots accepted by the reference indexer."""

    roots = tuple(trusted_roots) if trusted_roots is not None else tuple(
        library / "steamapps" / "common"
        for library in discover_steam_library_roots()
    )
    if trusted_roots is None and db_path != Path(VANILLA_REFERENCE_DB_PATH):
        roots = (db_path.parent, *roots)
    return tuple(
        os.path.normcase(os.path.realpath(os.path.expanduser(os.fspath(root))))
        for root in roots
    )
