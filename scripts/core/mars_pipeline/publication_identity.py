"""Project-scoped local identity for complete Mars source-copy publications."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import uuid

from scripts.app_settings import APP_DATA_DIR
from scripts.core.mars_pipeline.delivery_metadata import _source_copy_mod_id
from scripts.core.services.mars_mod_metadata import MetadataParseError, _tokens, _value_end

_MAX_STEAM_ID = 2**64 - 1
_ID_RE = re.compile(r"[1-9][0-9]{0,19}\Z")
_LOCK = threading.RLock()


class PublicationIdentityError(ValueError):
    """Raised when a local publication identity is invalid or stale."""

    def __init__(self, message: str, status: int = 422, code: str = "invalid_publication_identity"):
        super().__init__(message)
        self.status, self.code = status, code


def _storage_path(project_id: str) -> Path:
    if not isinstance(project_id, str) or not project_id or len(project_id) > 512:
        raise PublicationIdentityError("A valid project identity is required.")
    root = Path(APP_DATA_DIR) / "mars_pipeline" / "publications"
    for candidate in (root, *root.parents):
        if candidate.exists() or candidate.is_symlink():
            info = candidate.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise PublicationIdentityError("Publication storage cannot traverse links or junctions.")
    root.mkdir(parents=True, exist_ok=True)
    if root.resolve() != root.absolute():
        raise PublicationIdentityError("Publication storage must not be redirected.")
    key = hashlib.sha256(project_id.encode("utf-8")).hexdigest()
    path = root / f"{key}.json"
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise PublicationIdentityError("Publication binding storage is not a regular file.")
    return path


def validate_steam_id(value: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise PublicationIdentityError("Steam Workshop ID must be a positive unsigned 64-bit integer written as digits.")
    if int(value) > _MAX_STEAM_ID:
        raise PublicationIdentityError("Steam Workshop ID exceeds the unsigned 64-bit range.")
    return value


def read_source_workshop_id(source_root: str | Path) -> str | None:
    """Read only a literal top-level steam_id from inert metadata.lua tokens."""
    root = Path(source_root)
    path = root / "metadata.lua"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise PublicationIdentityError("Source metadata is redirected or too large.")
    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise PublicationIdentityError("Source metadata cannot be read as UTF-8.") from error
    try:
        tokens = _tokens(source.removeprefix("\ufeff"))
    except MetadataParseError as error:
        raise PublicationIdentityError("Source metadata has malformed Lua syntax.") from error
    prefix = [("ATOM", "return"), ("ATOM", "PlaceObj"), ("(", "("),
              ("STRING", "ModDef"), (",", ","), ("{", "{")]
    if tokens[:len(prefix)] != prefix:
        raise PublicationIdentityError("Source metadata has an unsupported top-level structure.")
    index = len(prefix)
    source_ids: list[str] = []
    while index < len(tokens) and tokens[index][0] != "}":
        if tokens[index][0] != "STRING" or index + 1 >= len(tokens) or tokens[index + 1][0] != ",":
            raise PublicationIdentityError("Source metadata has an unsupported top-level field.")
        key = tokens[index][1]
        start = index + 2
        try:
            end = _value_end(tokens, start)
        except MetadataParseError as error:
            raise PublicationIdentityError("Source metadata has malformed top-level values.") from error
        if key == "steam_id":
            if end != start + 1 or tokens[start][0] not in {"STRING", "ATOM"}:
                raise PublicationIdentityError("Source steam_id must be a literal value.")
            raw = tokens[start][1]
            if not raw.isdigit():
                raise PublicationIdentityError("Source steam_id is not a numeric Workshop ID.")
            source_ids.append(raw)
        if end >= len(tokens):
            break
        index = end + (1 if tokens[end][0] == "," else 0)
    if len(source_ids) > 1:
        raise PublicationIdentityError("Source metadata contains duplicate top-level steam_id fields.")
    if not source_ids or source_ids[0] == "0":
        return None
    return validate_steam_id(source_ids[0])


def _scope(project_id: str, receipt: dict) -> tuple[str, str, str | None]:
    if receipt.get("project_id") != project_id or receipt.get("status") != "prepared":
        raise PublicationIdentityError("Project has no matching prepared Mars source.", 409, "source_preparation_required")
    manifest = receipt.get("manifest") or {}
    source_id = str(manifest.get("mod_id") or "")
    if not source_id:
        raise PublicationIdentityError("Prepared source Mod ID is missing.")
    output_id = _source_copy_mod_id(source_id)
    source_workshop_id = read_source_workshop_id(receipt["source_path"])
    return source_id, output_id, source_workshop_id


def _read_record(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        info = path.lstat()
    except OSError as error:
        raise PublicationIdentityError("Publication binding cannot be inspected safely.") from error
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise PublicationIdentityError("Publication binding must be a regular, non-reparse file.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PublicationIdentityError("Publication binding is corrupt; it cannot be treated as unbound.") from error
    if (not isinstance(value, dict) or value.get("schema_version") != 1
            or isinstance(value.get("revision"), bool)
            or not isinstance(value.get("revision"), int) or value["revision"] < 1):
        raise PublicationIdentityError("Publication binding has an unsupported or corrupt record.")
    try:
        validate_steam_id(value.get("steam_id"))
    except PublicationIdentityError as error:
        raise PublicationIdentityError("Publication binding contains an invalid Steam ID.") from error
    if not all(isinstance(value.get(key), str) and value[key] for key in ("source_mod_id", "output_mod_id")):
        raise PublicationIdentityError("Publication binding scope is corrupt.")
    return value


def _state(project_id: str, receipt: dict, record: dict | None) -> dict:
    source_id, output_id, source_workshop_id = _scope(project_id, receipt)
    if record is not None:
        if record["source_mod_id"] != source_id or record["output_mod_id"] != output_id:
            raise PublicationIdentityError("Publication binding belongs to a different prepared Mod identity.", 409, "publication_scope_changed")
        if record["steam_id"] == source_workshop_id:
            raise PublicationIdentityError("Publication binding matches the source Workshop ID and is unsafe.", 409, "source_workshop_id_conflict")
    steam_id = record["steam_id"] if record else None
    return {"status": "bound" if record else "unbound", "revision": record["revision"] if record else 0,
            "steam_id": steam_id,
            "url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={steam_id}" if steam_id else None,
            "source_mod_id": source_id, "output_mod_id": output_id}


def get_publication_binding(project_id: str, receipt: dict) -> dict:
    """Resolve durable identity and fail closed on corrupt or stale scope."""
    with _LOCK:
        return _state(project_id, receipt, _read_record(_storage_path(project_id)))


def bind_publication_id(project_id: str, receipt: dict, steam_id: str,
                        expected_revision: int | None, approved: bool) -> dict:
    """Persist a user-entered local identity using optimistic concurrency."""
    if approved is not True:
        raise PublicationIdentityError("Explicit approval is required to bind a Workshop ID.")
    normalized = validate_steam_id(steam_id)
    with _LOCK:
        path = _storage_path(project_id)
        current = _read_record(path)
        state = _state(project_id, receipt, current)
        if expected_revision != state["revision"]:
            raise PublicationIdentityError("Publication binding changed; refresh before saving.", 409, "publication_revision_conflict")
        if state["status"] == "bound":
            raise PublicationIdentityError("A publication ID is already bound; replacing it requires an explicit reset flow.", 409, "publication_already_bound")
        if normalized == read_source_workshop_id(receipt["source_path"]):
            raise PublicationIdentityError("The output Workshop ID cannot equal the source Mod Workshop ID.", 409, "source_workshop_id_conflict")
        record = {"schema_version": 1, "revision": 1, "steam_id": normalized,
                  "source_mod_id": state["source_mod_id"], "output_mod_id": state["output_mod_id"]}
        temporary = path.with_name(f".{path.stem}-{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return _state(project_id, receipt, record)
