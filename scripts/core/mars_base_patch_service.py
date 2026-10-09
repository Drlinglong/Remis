"""Create independent editable base-game language Mods from verified origins."""
import csv
import hashlib
import io
import json
from pathlib import Path
import time
from types import SimpleNamespace

from scripts.core import surviving_mars_csv
from scripts.core.batch_artifacts import fingerprint
from scripts.core.batch_repository import BatchConflict
from scripts.core.batch_sources import freeze_sources, require_current_sources
from scripts.core.mars_base_patch_validation import (
    community_rows, conversion_origins, native_origins, read_snapshot, validate_candidates,
)
from scripts.core.mars_pipeline.cover_asset import read_cover_snapshot
from scripts.core.services.mars_translation_package import _lua_string


def render_patch(source, candidates, metadata, cover):
    mod_id = metadata["mod_id"]
    relative = "Localization/Schinese/Game.csv"
    mounted = f"Mod/{mod_id}/{relative}"
    translations = {row["id"]: row["translation"] for row in candidates["entries"]}
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(surviving_mars_csv.HEADER)
    for row in source.rows[source.header_row_index + 1:]:
        if row and row[1].strip():
            writer.writerow([row[0], row[1], translations[row[0]], row[3], row[4]])
    text = stream.getvalue()
    surviving_mars_csv.parse_text(text)
    fields = {k: metadata[k] for k in ("title", "description", "short_description", "last_changes", "author")}
    fields.update(id=mod_id, image=f"Mod/{mod_id}/Images/Cover{cover['extension']}")
    lines = ["return PlaceObj('ModDef', {"]
    lines.extend(f"  '{key}', {_lua_string(value)}," for key, value in fields.items())
    lines.extend(["  'version_major', 1,", "  'version_minor', 0,", "  'version', 1,",
                  "  'lua_revision', 350453,", "  'saved_with_revision', 406343,",
                  "  'optional_mod', true,",
                  "  'TagTranslations', true,", "  'loctables', {",
                  f"    {{ filename = {_lua_string(mounted)}, language = \"Schinese\" }},", "  },", "})", ""])
    items = ("return {\n  PlaceObj('ModItemLocTable', {\n    'language', \"Schinese\",\n"
             f"    'filename', {_lua_string(mounted)},\n  }}),\n}}\n")
    return {"metadata.lua": "\n".join(lines).encode("utf-8"), "items.lua": items.encode("utf-8"),
            relative: text.encode("utf-8"), f"Images/Cover{cover['extension']}": cover["data"]}


class MarsBasePatchService:
    def __init__(self, batch, output_root):
        self.batch, self.output_root = batch, Path(output_root)

    async def plan(self, request):
        snapshot = await freeze_sources(self.batch.manager, SimpleNamespace(
            project_id=request.project_id, file_ids=[request.file_id], source_column="Text"))
        if snapshot["adapter_id"] != "surviving_mars_csv":
            raise BatchConflict("game_mismatch", "This exporter only supports Mars CSV.")
        selected = next(file for file in snapshot["files"] if file["selected"])
        source = surviving_mars_csv.parse_text(selected["content"])
        candidates = json.loads(read_snapshot(request.candidates_path, request.candidates_sha256).decode("utf-8"))
        old_data = read_snapshot(request.community_csv_path, request.community_csv_sha256)
        old_rows = community_rows(old_data)
        report = validate_candidates(source, candidates, old_rows,
            conversion_origins(self.batch, request.conversion_job_ids), native_origins(self.batch, request.native_job_ids))
        cover = read_cover_snapshot(request.cover_asset_path, request.cover_asset_sha256)
        metadata = request.metadata.model_dump()
        generated = render_patch(source, candidates, metadata, cover)
        artifacts = self.batch.artifacts
        frozen = {"request": request.model_dump(), "source_artifact": artifacts.put(snapshot),
                  "candidates_artifact": artifacts.put(candidates), "report_artifact": artifacts.put(report),
                  "community_sha256": request.community_csv_sha256,
                  "files": {name: hashlib.sha256(data).hexdigest() for name, data in generated.items()}}
        identifier = "mars_base_" + fingerprint(frozen)[:24]
        record = {"id": identifier, "project_id": request.project_id, "created_at": time.time(),
                  "frozen": frozen, "status": "ready", "validation": report,
                  "risk": {"may_use_paid_api": False, "installs_to_game": False, "overwrites_original": False},
                  "allowed_actions": ["approve_export"], "runtime_verified": False}
        # A repeated preview retains the prior export receipt rather than resetting it.
        try:
            return self.batch.repository.get(identifier, "mars_base_plan")
        except BatchConflict as error:
            if error.status != 404:
                raise
        return self.batch.repository.put("mars_base_plan", record)

    async def export(self, identifier, approved):
        if not approved:
            raise BatchConflict("approval_required", "Approve this local package export.")
        record = self.batch.repository.get(identifier, "mars_base_plan")
        frozen = record["frozen"]
        snapshot = self.batch.artifacts.get(frozen["source_artifact"])
        await require_current_sources(self.batch.manager, snapshot)
        request = frozen["request"]
        source = surviving_mars_csv.parse_text(next(f["content"] for f in snapshot["files"] if f["selected"]))
        cover = read_cover_snapshot(request["cover_asset_path"], request["cover_asset_sha256"])
        files = render_patch(source, self.batch.artifacts.get(frozen["candidates_artifact"]), request["metadata"], cover)
        hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        if hashes != frozen["files"]:
            raise BatchConflict("package_snapshot_changed", "Package changed since its preview.")
        destination = self.output_root / identifier / request["metadata"]["mod_id"]
        if destination.exists():
            if record.get("status") != "exported" or any(not (destination / name).is_file()
                    or hashlib.sha256((destination / name).read_bytes()).hexdigest() != digest for name, digest in hashes.items()):
                raise BatchConflict("output_exists", "Existing or partial output requires inspection; nothing was overwritten.")
            return record
        destination.mkdir(parents=True, exist_ok=False)
        for name, data in files.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(data)
        receipt = {"plan_id": identifier, "mod_id": request["metadata"]["mod_id"], "files": hashes,
                   "validation": record["validation"], "runtime_verified": False, "published": False}
        (destination.parent / "delivery-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.batch.repository.update(identifier, {"status": "exported", "output_path": str(destination),
            "exported_at": time.time(), "allowed_actions": ["inspect_local_output", "manual_install"]})
