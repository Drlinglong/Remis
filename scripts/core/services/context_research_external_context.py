"""Bounded metadata and Steam Workshop context for archive research.

The research harness may use project metadata and an optional public Steam
Workshop item as supporting context.  This module owns path resolution,
sanitisation, provenance, and the read-only Workshop request.  It never
translates, persists, or publishes external content.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from scripts.app_settings import GAME_ID_ALIASES, GAME_PROFILES_BY_ID


LOGGER = logging.getLogger(__name__)
STEAM_WORKSHOP_DETAILS_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/"
    "GetPublishedFileDetails/v1/"
)
MAX_METADATA_TEXT = 1_200
MAX_WORKSHOP_DESCRIPTION = 2_000


class ExternalContextSource(BaseModel):
    """Auditable status for one optional external context source."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    kind: str = Field(min_length=1, max_length=40)
    locator: str = Field(min_length=1, max_length=500)
    status: str = Field(min_length=1, max_length=40)
    sha256: str | None = Field(default=None, max_length=64)
    error_code: str | None = Field(default=None, max_length=80)


class ContextResearchExternalContext(BaseModel):
    """Sanitised, bounded context available to Lead and universal-context synthesis."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    game_id: str = Field(default="", max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)
    metadata_source: ExternalContextSource | None = None
    workshop: dict[str, Any] = Field(default_factory=dict)
    workshop_source: ExternalContextSource | None = None


def normalize_workshop_item_id(value: Any) -> str | None:
    """Accept only a numeric Steam published-file ID, without guessing."""

    text = str(value or "").strip()
    return text if re.fullmatch(r"\d{1,20}", text) else None


def resolve_metadata_path(
    source_root: str | Path | None,
    game_id: str | None = None,
) -> Path | None:
    """Resolve the configured metadata file for any supported Paradox game."""

    if not source_root:
        return None
    root = Path(source_root)
    if root.is_file():
        root = root.parent
    root = _normalize_mod_root(root, game_id)
    profile = _game_profile(game_id)
    configured = str(profile.get("metadata_file", "")).strip()
    relative_paths = [configured, ".metadata/metadata.json", "descriptor.mod", ".descriptor.mod"]
    seen: set[str] = set()
    for relative in relative_paths:
        if not relative:
            continue
        candidate = root / Path(relative.replace("\\", "/"))
        key = str(candidate).casefold()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate
    return None


def load_external_context(
    source_root: str | Path | None,
    game_id: str | None = None,
    workshop_item_id: str | None = None,
    *,
    workshop_opener: Callable[..., Any] | None = None,
) -> ContextResearchExternalContext:
    """Read local metadata and optionally one public Workshop item."""

    normalized_game = _normalized_game_id(game_id)
    metadata, metadata_source = _load_metadata(source_root, normalized_game)
    workshop, workshop_source = _load_workshop(workshop_item_id, workshop_opener)
    return ContextResearchExternalContext(
        game_id=normalized_game,
        metadata=metadata,
        metadata_source=metadata_source,
        workshop=workshop,
        workshop_source=workshop_source,
    )


def prompt_context_payload(context: ContextResearchExternalContext | None) -> dict[str, Any]:
    """Expose only bounded semantic fields to the model prompt."""

    if context is None:
        return {}
    return {
        "game_id": context.game_id,
        "metadata": context.metadata,
        "workshop": context.workshop,
        "available_sources": [
            source.kind
            for source in (context.metadata_source, context.workshop_source)
            if source is not None and source.status == "loaded"
        ],
    }


def _load_metadata(
    source_root: str | Path | None,
    game_id: str,
) -> tuple[dict[str, Any], ExternalContextSource | None]:
    path = resolve_metadata_path(source_root, game_id)
    if path is None:
        return {}, ExternalContextSource(
            kind="mod_metadata", locator="configured_game_profile", status="missing",
            error_code="metadata_file_not_found",
        )
    try:
        raw = path.read_text(encoding="utf-8-sig")
        payload = _parse_metadata(raw, path)
        return payload, ExternalContextSource(
            kind="mod_metadata", locator=str(path), status="loaded",
            sha256=_sha256(raw.encode("utf-8")),
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        LOGGER.warning("Unable to read mod metadata from %s: %s", path, type(error).__name__)
        return {}, ExternalContextSource(
            kind="mod_metadata", locator=str(path), status="error",
            error_code=type(error).__name__,
        )


def _load_workshop(
    workshop_item_id: str | None,
    opener: Callable[..., Any] | None,
) -> tuple[dict[str, Any], ExternalContextSource | None]:
    if not workshop_item_id:
        return {}, ExternalContextSource(
            kind="steam_workshop", locator="not_requested", status="not_requested",
        )
    normalized = normalize_workshop_item_id(workshop_item_id)
    locator = f"steam_workshop:{str(workshop_item_id).strip()}"
    if normalized is None:
        return {}, ExternalContextSource(
            kind="steam_workshop", locator=locator, status="rejected",
            error_code="invalid_workshop_item_id",
        )
    try:
        payload = _fetch_workshop(normalized, opener)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return payload, ExternalContextSource(
            kind="steam_workshop", locator=f"steam_workshop:{normalized}", status="loaded",
            sha256=_sha256(encoded),
        )
    except Exception as error:  # network and remote-schema failures are non-fatal context gaps
        LOGGER.warning("Unable to read Steam Workshop item %s: %s", normalized, type(error).__name__)
        return {}, ExternalContextSource(
            kind="steam_workshop", locator=f"steam_workshop:{normalized}", status="error",
            error_code=type(error).__name__,
        )


def _fetch_workshop(item_id: str, opener: Callable[..., Any] | None) -> dict[str, Any]:
    request = Request(
        STEAM_WORKSHOP_DETAILS_URL,
        data=urlencode({"itemcount": "1", "publishedfileids[0]": item_id}).encode("ascii"),
        headers={"User-Agent": "Remis-context-research/3.2.0"},
        method="POST",
    )
    open_url = opener or urlopen
    with open_url(request, timeout=15) as response:
        raw = response.read(512_000)
    body = json.loads(raw.decode("utf-8"))
    details = body.get("response", {}).get("publishedfiledetails", [])
    if not details or details[0].get("result") != 1:
        raise ValueError("steam_workshop_item_unavailable")
    item = details[0]
    return {
        "publishedfileid": item_id,
        "title": _text(item.get("title"), 300),
        "description": _text(item.get("description"), MAX_WORKSHOP_DESCRIPTION),
        "tags": [_text(tag.get("tag"), 80) for tag in item.get("tags", []) if isinstance(tag, Mapping)][:20],
        "time_updated": _text(item.get("time_updated"), 40),
        "creator_app_id": _text(item.get("creator_app_id"), 40),
        "consumer_app_id": _text(item.get("consumer_app_id"), 40),
    }


def _parse_metadata(raw: str, path: Path) -> dict[str, Any]:
    if path.name.casefold() == "metadata.json":
        data = json.loads(raw)
        if not isinstance(data, Mapping):
            raise ValueError("metadata_json_root_must_be_object")
        return _metadata_payload(data)
    return _metadata_payload(_parse_descriptor(raw))


def _metadata_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        key: _text(data.get(key), MAX_METADATA_TEXT)
        for key in ("name", "short_description", "version", "supported_game_version", "path", "remote_file_id")
        if data.get(key) not in (None, "")
    }
    for key in ("tags", "relationships"):
        values = data.get(key)
        if isinstance(values, list):
            payload[key] = [_text(item, 120) for item in values[:20]]
    custom = data.get("game_custom_data")
    if isinstance(custom, Mapping):
        payload["game_custom_data"] = {
            _text(key, 80): _text(value, 240) for key, value in list(custom.items())[:20]
        }
    return payload


def _parse_descriptor(raw: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw.splitlines():
        match = re.match(r"^\s*([A-Za-z_][\w]*)\s*=\s*(?:\"([^\"]*)\"|([^#\s]+))", line)
        if match and match.group(1) in {"name", "path", "remote_file_id", "supported_version", "version", "tags"}:
            values[match.group(1)] = match.group(2) or match.group(3) or ""
    if "supported_version" in values and "supported_game_version" not in values:
        values["supported_game_version"] = values.pop("supported_version")
    return values


def _normalize_mod_root(root: Path, game_id: str | None) -> Path:
    profile = _game_profile(game_id)
    localization = str(profile.get("source_localization_folder", "")).casefold()
    if root.name.casefold() in {".metadata", "metadata.json", "descriptor.mod", ".descriptor.mod"}:
        root = root.parent
    if localization and root.name.casefold() == localization:
        root = root.parent
    return root


def _game_profile(game_id: str | None) -> Mapping[str, Any]:
    return GAME_PROFILES_BY_ID.get(_normalized_game_id(game_id), {})


def _normalized_game_id(game_id: str | None) -> str:
    value = str(game_id or "").strip().casefold()
    return str(GAME_ID_ALIASES.get(value, value))


def _text(value: Any, limit: int) -> str:
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = str(value or "").strip()
    return text[: max(0, limit - 1)] + "…" if len(text) > limit else text


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = [
    "ContextResearchExternalContext",
    "ExternalContextSource",
    "STEAM_WORKSHOP_DETAILS_URL",
    "load_external_context",
    "normalize_workshop_item_id",
    "prompt_context_payload",
    "resolve_metadata_path",
]
