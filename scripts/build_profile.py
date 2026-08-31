"""Small, shared boundary for stable and Agent Preview build identity."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


STABLE_CHANNEL = "stable"
AGENT_PREVIEW_CHANNEL = "agent-preview"


@dataclass(frozen=True)
class BuildProfile:
    channel: str
    product_name: str
    version: str
    identifier: str
    app_data_folder: str
    backend_port: int
    copilot_enabled: bool


PROFILES = {
    STABLE_CHANNEL: BuildProfile(
        channel=STABLE_CHANNEL,
        product_name="remis-mod-factory",
        version="3.1.8",
        identifier="com.remis.modfactory",
        app_data_folder="RemisModFactory",
        backend_port=1453,
        copilot_enabled=False,
    ),
    AGENT_PREVIEW_CHANNEL: BuildProfile(
        channel=AGENT_PREVIEW_CHANNEL,
        product_name="Remis Agent Preview",
        version="3.1.7-agent-preview.1",
        identifier="com.remis.modfactory.agent-preview",
        app_data_folder="RemisAgentPreview",
        backend_port=1454,
        copilot_enabled=True,
    ),
}


def _bundled_channel() -> str | None:
    resource_root = getattr(sys, "_MEIPASS", None)
    if not resource_root:
        return None
    manifest = Path(resource_root) / "data" / "build_profile.json"
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    channel = payload.get("channel")
    return channel if channel in PROFILES else None


def get_build_profile() -> BuildProfile:
    configured = os.getenv("REMIS_BUILD_CHANNEL")
    channel = configured.strip().lower() if configured else None
    if channel not in PROFILES:
        channel = _bundled_channel() or STABLE_CHANNEL
    return PROFILES[channel]


def runtime_app_data_folder(
    profile: BuildProfile | None = None,
    *,
    frozen: bool | None = None,
) -> str:
    """Return the isolated data folder for packaged and development runtimes."""
    selected = profile or get_build_profile()
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        return selected.app_data_folder
    if selected.channel == AGENT_PREVIEW_CHANNEL:
        return f"{selected.app_data_folder}Dev"
    return "RemisModFactoryDev"


def write_profile_manifest(profile: BuildProfile, path: str | os.PathLike[str]) -> None:
    payload = {
        "channel": profile.channel,
        "product_name": profile.product_name,
        "version": profile.version,
        "identifier": profile.identifier,
        "app_data_folder": profile.app_data_folder,
        "backend_port": profile.backend_port,
        "copilot_enabled": profile.copilot_enabled,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
