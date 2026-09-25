"""Conservative, profile-bound runtime overlay source generation for Mars mods."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


PROFILE_MOD_ID = "kz4dEz"
UPGRADE_PROFILE = {
    "SAEM_Accumulator_TrickleCharge": ("Code/Exotics_AccumulatorUpgrade.lua", "Exotic Energy Synthesis"),
    "ExoticsUpgrade_ExoticShielding": ("Code/Exotics_PowerProducersUpgrade.lua", "Exotic Shielding"),
    "ExoticsUpgrade_ExoticTargetingModels": ("Code/Exotics_MDSLaserUpgrade.lua", "Exotic Targeting Models"),
    "ExoticsUpgrade_HarmonicActuators": ("Code/Exotics_TriboelectricScrubberUpgrade.lua", "Exotic Harmonic Actuators"),
    "ExoticsUpgrade_ThermalDistributors": ("Code/Exotics_SubsurfaceHeaterUpgrade.lua", "Exotic Thermal Distributors"),
    "ExoticsUpgrade_LogisticsMesh": ("Code/Exotics_ShuttleHubUpgrade.lua", "Exotic Logistics Mesh"),
    "ExoticsUpgrade_SeedDispersal": ("Code/Exotics_ForestationPlantUpgrade.lua", "Exotic Seed Dispersal Array"),
    "ExoticsUpgrade_CognitiveLattice": ("Code/Exotics_SanatoriumUpgrade.lua", "Exotic Cognitive Lattice"),
}
TECH_LABEL = ("Code/Exotics_TechTreeLabel.lua", "EXOTIC APPLICATIONS")


class OverlayProfileError(ValueError):
    """Raised when source evidence does not match the reviewed overlay profile."""


def _entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = manifest.get("entries", {})
    if isinstance(raw, list):
        rows = {str(row.get("id")): row for row in raw if isinstance(row, dict)}
    elif isinstance(raw, dict):
        rows = {str(key): row for key, row in raw.items() if isinstance(row, dict)}
    else:
        raise OverlayProfileError("Manifest entries must be a list or mapping.")
    return rows


def _reference_match(row: dict[str, Any], path: str, english: str) -> bool:
    refs = row.get("refs", row.get("source_refs", []))
    return (row.get("text", row.get("source")) == english
            and any(isinstance(ref, dict) and ref.get("path") == path for ref in refs))


def _verify_constant(source_root: Path, path: str, field: str, expected: str) -> None:
    source_path = source_root.joinpath(*path.split("/"))
    try:
        content = source_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise OverlayProfileError(f"Unable to read reviewed binding source {path}.") from error
    pattern = re.compile(rf"\b{re.escape(field)}\s*=\s*(['\"]){re.escape(expected)}\1")
    if len(pattern.findall(content)) != 1:
        raise OverlayProfileError(f"Source binding {field} in {path} differs from the reviewed profile.")


def compile_overlay(manifest: dict[str, Any], source_id: str, source_root: Path) -> dict[str, Any]:
    """Bind exact, reviewed name/description candidates to stable upgrade IDs.

    This profile deliberately leaves dynamic upgrade descriptions, Mod Options,
    Telepath performance text, and other candidates uncovered for review.
    """
    if source_id != PROFILE_MOD_ID or manifest.get("mod_id") != PROFILE_MOD_ID:
        raise OverlayProfileError("Runtime overlay profile is guarded to source Mod kz4dEz.")
    source_root = Path(source_root).resolve(strict=True)
    entries = _entries(manifest)
    bindings: dict[str, dict[str, Any]] = {}
    supported: set[str] = set()
    for upgrade_id, (path, name_text) in UPGRADE_PROFILE.items():
        _verify_constant(source_root, path, "UPGRADE_ID", upgrade_id)
        matches = [(key, row) for key, row in entries.items()
                   if _reference_match(row, path, name_text) and not row.get("review_required", True)]
        if len(matches) != 1:
            raise OverlayProfileError(f"Expected one reviewed upgrade-name entry for {upgrade_id}; found {len(matches)}.")
        key, name_row = matches[0]
        if not key.isascii() or not key.isdecimal():
            raise OverlayProfileError(f"Upgrade-name ID is not a decimal localization ID: {key}.")
        bindings[upgrade_id] = {"display_name": {"id": int(key), "english": name_text}}
        supported.add(key)

    label_matches = [(key, row) for key, row in entries.items()
                     if _reference_match(row, *TECH_LABEL) and not row.get("review_required", True)]
    label_binding = None
    _verify_constant(source_root, TECH_LABEL[0], "LABEL_ID", "ExoticsApplications")
    if len(label_matches) == 2:
        keys = sorted((key for key, _ in label_matches), key=int)
        key = keys[0]
        if not key.isascii() or not key.isdecimal():
            raise OverlayProfileError("Tech label ID must be decimal.")
        label_binding = {"id": int(key), "english": TECH_LABEL[1]}
        # The source assigns the same label at construction and refresh sites.
        # Keep both persisted source IDs in the locale table; the bridge uses the
        # first numeric ID after verifying both source occurrences match exactly.
        supported.update(keys)
    elif label_matches:
        raise OverlayProfileError("Expected both reviewed tech-label source occurrences.")

    unresolved = sorted(set(entries) - supported)
    lua = _overlay_lua(bindings, label_binding)
    return {
        "profile": "exotic-minerals-expanded-kz4dEz-v1",
        "supported_ids": sorted(supported, key=int),
        "uncovered_ids": unresolved,
        "complete": not unresolved,
        "lua": lua,
        "profile_fingerprint": hashlib.sha256(lua.encode("utf-8")).hexdigest(),
    }


def _lua_value(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"[{_lua_value(key)}] = {_lua_value(item)}" for key, item in value.items()
        ) + "}"
    if isinstance(value, list):
        return "{" + ", ".join(_lua_value(item) for item in value) + "}"
    raise OverlayProfileError("Unsupported data in generated Lua binding.")


def _overlay_lua(bindings: dict[str, Any], label_binding: dict[str, Any] | None) -> str:
    """Render a Lua bridge using stable IDs and exact source-name guards."""
    bindings_source = _lua_value(bindings)
    label_source = _lua_value(label_binding)
    return f'''-- Generated by Remis for the reviewed Exotic Minerals Expanded profile.
-- Language-neutral IDs; the active game language selects the registered CSV.
local PROFILE_SOURCE_MOD = "kz4dEz"
local UPGRADE_BINDINGS = {bindings_source}
local TECH_LABEL = {label_source}

local function patch_table(target)
  if type(target) ~= "table" then return end
  local max = const and const.Building and const.Building.MaxUpgrades or 0
  for tier = 1, max do
    local prefix = "upgrade" .. tostring(tier) .. "_"
    local binding = UPGRADE_BINDINGS[rawget(target, prefix .. "id")]
    if binding then
      if binding.display_name then
        target[prefix .. "display_name"] = T(binding.display_name.id, binding.display_name.english)
      end
      if binding.description then
        target[prefix .. "description"] = T(binding.description.id, binding.description.english)
      end
    end
  end
end

local function patch_all()
  if not BuildingTemplates or not g_Classes then return end
  for _, template in pairs(BuildingTemplates) do patch_table(template) end
  for _, class in pairs(g_Classes) do patch_table(class) end
  local city = rawget(_G, "UICity") or rawget(_G, "CurrentMap")
  if city and type(city.MapForEach) == "function" then
    city:MapForEach("map", "UpgradableBuilding", patch_table)
  end
  local label = Presets and Presets.XPresetMapLabel and Presets.XPresetMapLabel.Tech
      and Presets.XPresetMapLabel.Tech.ExoticsApplications
  if label and TECH_LABEL then label.Text = T(TECH_LABEL.id, TECH_LABEL.english) end
end

function OnMsg.ClassesPostprocess() patch_all() end
function OnMsg.LoadGame() patch_all() end
function OnMsg.PostLoadGame() patch_all() end
function OnMsg.GameTimeStart() patch_all() end
function OnMsg.MapGameTimeStart() patch_all() end
function OnMsg.BuildingConstructed(building) patch_table(building) end
function OnMsg.Autorun() patch_all() end
function OnMsg.ModsReloaded() patch_all() end
'''
