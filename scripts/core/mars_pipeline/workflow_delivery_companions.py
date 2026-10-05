"""Resolve governed optional Mars projects into conditionally loaded tables."""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict

from scripts.core.services import mars_translation_package as package


def _lua_string(value: str) -> str:
    return package._lua_string(value)


def _render_loader(tables: list[dict], snapshot_digest: str) -> bytes:
    table_rows = []
    for table in tables:
        owners = ", ".join(_lua_string(value) for value in table["owners"])
        ids = ", ".join(str(int(value)) for value in table["ids"])
        table_rows.append(
            "  {owners={" + owners + "}, ids={" + ids + "}, language="
            + _lua_string(table["language"]) + ", path=" + _lua_string(table["path"]) + "},"
        )
    lines = [
        "-- Governed companion snapshot " + snapshot_digest,
        "local tables = {", *table_rows, "}",
        "local missing = {}",
        "local applied_table, previous, applied = nil, {}, {}",
        "local function enabled_ids()",
        "  local enabled = {}",
        "  for _, mod in ipairs(ModsLoaded or {}) do",
        "    if type(mod) == 'table' and type(mod.id) == 'string' then enabled[mod.id] = true end",
        "  end",
        "  return enabled",
        "end",
        "local function restore()",
        "  if applied_table ~= TranslationTable then previous, applied = {}, {} end",
        "  if type(TranslationTable) == 'table' then",
        "    for id, old in pairs(previous) do",
        "      if TranslationTable[id] == applied[id] then",
        "        if old == missing then TranslationTable[id] = nil else TranslationTable[id] = old end",
        "      end",
        "    end",
        "  end",
        "  previous, applied, applied_table = {}, {}, TranslationTable",
        "end",
        "local function sync_companion_localization()",
        "  if type(TranslationTable) ~= 'table' then return end",
        "  local enabled = enabled_ids()",
        "  restore()",
        "  for _, table_info in ipairs(tables) do",
        "    local active = false",
        "    for _, owner in ipairs(table_info.owners) do if enabled[owner] then active = true; break end end",
        "    if active and GetLanguage() == table_info.language then",
        "      for _, id in ipairs(table_info.ids) do if previous[id] == nil then previous[id] = TranslationTable[id] or missing end end",
        "      LoadTranslationTableFile(table_info.path)",
        "      for _, id in ipairs(table_info.ids) do applied[id] = TranslationTable[id] end",
        "    end",
        "  end",
        "end",
        "OnMsg = OnMsg or {}",
        "local previous_mods_reloaded = OnMsg.ModsReloaded",
        "OnMsg.ModsReloaded = function(...) if previous_mods_reloaded then previous_mods_reloaded(...) end; sync_companion_localization() end",
        "local previous_translation_changed = OnMsg.TranslationChanged",
        "OnMsg.TranslationChanged = function(...) if previous_translation_changed then previous_translation_changed(...) end; sync_companion_localization() end",
        "sync_companion_localization()",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


async def build_bundle(
    base_project_id: str,
    base_receipt: dict,
    base_translations: dict[str, dict[str, str]],
    outputs: list[dict],
    expected_snapshots: list[dict] | None = None,
) -> dict | None:
    if not outputs:
        return None
    snapshots: list[dict] = []
    rows_by_language: dict[str, dict[str, dict]] = defaultdict(dict)
    seen_selections: set[tuple[str, str]] = set()
    for selection in outputs:
        language = selection["language_code"]
        identity = (selection["project_id"], language)
        if identity in seen_selections:
            raise ValueError("Select each companion project and target language only once")
        seen_selections.add(identity)
        snapshot, rows = await _resolve_selection(base_project_id, base_translations, selection)
        snapshots.append(snapshot)
        _merge_rows(rows_by_language[language], rows)
    if expected_snapshots is not None and snapshots != expected_snapshots:
        raise ValueError("A companion source or translation output changed after preview")
    return _render_bundle(base_receipt, base_translations, rows_by_language, snapshots)


async def _resolve_selection(base_project_id: str, base_translations: dict, selection: dict) -> tuple[dict, dict]:
    from scripts.core.mars_pipeline import delivery, workflow_delivery as workflow
    project_id = selection["project_id"]
    language = selection["language_code"]
    if project_id == base_project_id:
        raise ValueError("The base project cannot also be selected as an additional project")
    if language not in base_translations:
        raise ValueError("Each companion target language must also be selected for the base project")
    project, receipt = await workflow._context(project_id)
    if project.get("game_id") != "surviving_mars" or not receipt["manifest"].get("mod_id"):
        raise ValueError("Additional project must be a prepared Surviving Mars Mod")
    translated = workflow._read_translations(project, receipt["manifest"], [selection], "text_only")[language]
    preview = await asyncio.to_thread(delivery.inspect_delivery, receipt["source_path"],
                                      receipt["manifest"], {language: translated}, "text_only")
    snapshot = {"project_id": project_id, "run_id": receipt["run_id"],
                "mod_id": receipt["manifest"]["mod_id"], "language_code": language,
                "output_folder_name": selection["output_folder_name"],
                "source_fingerprint": preview["source_fingerprint"],
                "output_fingerprint": preview["fingerprint"]}
    approved = set(receipt["manifest"].get("approved_ids", []))
    rows = {key: {"source": receipt["manifest"]["entries"][key]["text"], "target": value,
                  "owners": {receipt["manifest"]["mod_id"]}}
            for key, value in translated.items()
            if key in approved and receipt["manifest"]["entries"].get(key, {}).get("kind") == "existing_t"}
    return snapshot, rows


def _merge_rows(target: dict[str, dict], incoming: dict[str, dict]) -> None:
    for key, row in incoming.items():
        existing = target.get(key)
        if existing and (existing["source"] != row["source"] or existing["target"] != row["target"]):
            field = "source" if existing["source"] != row["source"] else "target"
            raise ValueError(f"Companion {field} conflict for translation ID {key}")
        if existing:
            existing["owners"].update(row["owners"])
        else:
            target[key] = row


def _render_bundle(base_receipt: dict, base_translations: dict, rows_by_language: dict,
                   snapshots: list[dict]) -> dict:
    from scripts.core.mars_pipeline import delivery
    base_entries = base_receipt["manifest"]["entries"]
    base_approved = set(base_receipt["manifest"].get("approved_ids", []))
    for language, rows in rows_by_language.items():
        base_values = base_translations[language]
        for key in list(rows):
            row, base_row = rows[key], base_entries.get(key)
            if base_row:
                if key not in base_approved or base_row.get("kind") != "existing_t":
                    raise ValueError(f"Base/companion ID conflict for translation ID {key}")
                if base_row.get("text") != row["source"]:
                    raise ValueError(f"Base/companion source conflict for translation ID {key}")
                if base_values.get(key) != row["target"]:
                    raise ValueError(f"Base/companion target conflict for translation ID {key}")
                del rows[key]
    grouped: dict[tuple[str, tuple[str, ...]], list[str]] = defaultdict(list)
    output_files: dict[str, bytes] = {}
    for language, rows in rows_by_language.items():
        game_language = package._language(language)
        by_owners: dict[tuple[str, ...], dict[str, dict]] = defaultdict(dict)
        for key, row in rows.items():
            owners = tuple(sorted(row["owners"]))
            by_owners[owners][key] = row
        for owners, rows_for_owners in by_owners.items():
            digest = hashlib.sha256((language + "\0" + "\0".join(owners)).encode("utf-8")).hexdigest()[:12]
            relative = f"Localization/{game_language}/RemisOptional-{digest}.csv"
            values = {key: row["target"] for key, row in rows_for_owners.items()}
            entries_for_rows = {key: {"text": row["source"]} for key, row in rows_for_owners.items()}
            output_files[relative] = delivery._entry_rows(entries_for_rows, values, set(values)).encode("utf-8")
            grouped[(language, owners)].extend(rows_for_owners)
    table_specs = []
    snapshot_digest = hashlib.sha256(json.dumps(
        snapshots, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    for (language, owners), ids in sorted(grouped.items()):
        game_language = package._language(language)
        digest = hashlib.sha256((language + "\0" + "\0".join(owners)).encode("utf-8")).hexdigest()[:12]
        table_specs.append({
            "owners": list(owners), "ids": sorted(ids, key=int),
            "language": game_language,
            "path": f"Mod/{delivery_id_for(base_receipt)}/Localization/{game_language}/RemisOptional-{digest}.csv",
        })
    return {
        "files": output_files,
        "loader": _render_loader(table_specs, snapshot_digest),
        "snapshots": snapshots,
        "snapshot_fingerprint": snapshot_digest,
        "localized_ids": sorted({key for rows in rows_by_language.values() for key in rows}, key=int),
        "localized_ids_by_language": {language: sorted(rows, key=int) for language, rows in rows_by_language.items()},
    }


def delivery_id_for(receipt: dict) -> str:
    source_id = receipt["manifest"]["mod_id"]
    return "RemisText" + hashlib.sha256(f"remis-text-only\0{source_id}".encode("utf-8")).hexdigest()[:12]


def attach_bundle(plan: dict, bundle: dict) -> dict:
    generated = plan["generated"]
    generated.update(bundle["files"])
    generated["Code/RemisOptionalLocalization.lua"] = bundle["loader"]
    plan["selected_ids"].update(bundle["localized_ids"])
    for language, ids in bundle["localized_ids_by_language"].items():
        plan["selected_ids_by_language"].setdefault(language, set()).update(ids)
    plan.setdefault("conditional_ids", []).extend(bundle["localized_ids"])
    plan["companion_snapshots"] = bundle["snapshots"]
    return plan
