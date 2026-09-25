"""Bridge game resources into Remis's existing files, snapshots and writers.

There is no task runner, model client or translation database in this module.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .contracts import Document
from .registry import adapter_for_path, resource_adapter


MANIFEST = ".remis-localization-manifest.json"


def discover_files(root: str | Path, profile: dict, source_lang: dict) -> list[dict]:
    adapter = resource_adapter(profile)
    result = adapter.discover(Path(root), source_lang, profile.get("game_version"))
    errors = [issue for issue in result.diagnostics if issue.severity == "error"]
    if errors:
        raise ValueError("; ".join(f"{issue.code}: {issue.message}" for issue in errors))
    return [{
        "path": str(resource.path), "file_path": resource.relative_path,
        "filename": resource.path.name, "root": str(resource.path.parent),
        "loc_root": str(root), "is_custom_loc": False,
        "adapter_id": adapter.id,
        "adapter_metadata": {"source_root": str(root), **resource.metadata, "project_root": str(root)},
        "discovery_diagnostics": [issue.as_dict() for issue in result.diagnostics],
    } for resource in result.resources]


def extract_file(path: str | Path, adapter_id: str | None = None,
                 metadata: dict | None = None):
    adapter = resource_adapter(adapter_id) if adapter_id else adapter_for_path(path)
    document = adapter.parse(Path(path), metadata)
    return extract_document(document, adapter.id)


def extract_document(document: Document, adapter_id: str):
    errors = [issue for issue in document.metadata.get("diagnostics", [])
              if issue.get("severity") == "error"]
    if errors:
        raise ValueError("; ".join(f"{issue['code']}: {issue.get('message', '')}" for issue in errors))
    keys = [entry.key for entry in document.entries]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate localization keys in {document.path}")
    key_map = {index: {
        "key_part": entry.key, "line_num": entry.line_number - 1,
        "line_number": entry.line_number, "entry": entry,
        "adapter_id": adapter_id, "adapter_document": document,
    } for index, entry in enumerate(document.entries)}
    return (document.source_text.splitlines(keepends=True),
            [entry.value for entry in document.entries], key_map, ())


def build_snapshot(root: str, profile: dict, source_lang: dict, callback=None) -> list[dict]:
    files = []
    for item in discover_files(root, profile, source_lang):
        lines, texts, key_map, _ = extract_file(item["path"], item["adapter_id"], item["adapter_metadata"])
        entries = tuple(info["entry"] for info in key_map.values())
        files.append({**item, "full_path": Path(item["path"]),
                      "original_lines": lines, "parsed_entries": [e.as_legacy_tuple() for e in entries],
                      "canonical_entries": entries, "adapter_key_map": key_map,
                      "texts_to_translate": texts, "key_map": key_map,
                      "parse_summary": {"raw": len(entries), "syntax_parsed": len(entries),
                                        "eligible": len(entries), "policy_excluded": 0, "parse_errors": 0}})
    if callback:
        callback({"stage": "Scanning", "stage_code": "scanning_source", "percent": 10,
                  "files_detected": len(files), "message": f"Scanned {len(files)} files."})
    return files


def safe_output(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or ":" in relative_path:
        raise ValueError(f"Unsafe adapter output path: {relative_path}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError(f"Adapter output escapes package: {relative_path}")
    return target


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def write_document(document: Document, adapter_id: str, translations: list[str],
                   destination: str | Path, target_lang: dict) -> list[str]:
    """Render validated content into the workflow-owned language package."""
    if len(translations) != len(document.entries):
        raise ValueError("Translation count does not match the captured source document")
    adapter = resource_adapter(adapter_id)
    values = dict(zip((entry.key for entry in document.entries), translations))
    for entry in document.entries:
        issues = adapter.validate(entry.value, values[entry.key])
        if (entry.key not in document.metadata.get("needs_review_keys", [])
                and any(issue.severity == "error" for issue in issues)):
            raise ValueError(f"{entry.key}: " + "; ".join(issue.code for issue in issues))
    rendered = adapter.render(document, values, target_lang)
    _verify_rendered(adapter, rendered, values)
    root = Path(destination)
    source_root = Path(document.metadata.get("source_root", document.path.parent))
    metadata = adapter.package_metadata(source_root, target_lang, document.metadata.get("game_version"))
    if set(metadata) & set(rendered):
        raise ValueError("Adapter resource output conflicts with package metadata")
    paths = {name: safe_output(root, name) for name in {**metadata, **rendered}}
    manifest_path = safe_output(root, MANIFEST)
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("game_id") != adapter_id:
            raise ValueError("Output package belongs to another game")
        previous_mod = manifest.get("source_mod_id")
        current_mod = document.metadata.get("source_mod_id")
        if previous_mod and current_mod and previous_mod != current_mod:
            raise ValueError("Output package belongs to another source Mod")
        for name in rendered:
            previous = manifest.get("files", {}).get(name)
            project_root = Path(document.metadata.get("project_root", source_root)).resolve()
            current_source = document.path.resolve().relative_to(project_root).as_posix()
            if previous and previous.get("source_path") != current_source:
                raise ValueError(f"Multiple source resources would overwrite {name}")
    contents = {**metadata, **rendered,
                MANIFEST: _manifest_text(root, document, adapter_id, rendered, target_lang)}
    _write_package(root, contents)
    return [str(paths[name]) for name in rendered]


def _verify_rendered(adapter, rendered: dict[str, str], expected: dict[str, str]) -> None:
    observed = {}
    for relative, content in rendered.items():
        document = adapter.parse_text(content, Path(relative))
        extract_document(document, adapter.id)
        for entry in document.entries:
            if entry.key in observed:
                raise ValueError(f"Duplicate output resource key: {entry.key}")
            observed[entry.key] = entry.value
    if observed != expected:
        raise ValueError("Rendered resource does not preserve every translation key and value")


def _manifest_text(root: Path, document: Document, adapter_id: str,
                   rendered: dict[str, str], target_lang: dict) -> str:
    manifest_path = safe_output(root, MANIFEST)
    manifest = {"schema_version": 1, "game_id": adapter_id, "files": {}}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("game_id") != adapter_id:
            raise ValueError("Output package belongs to another game")
    source_root = Path(document.metadata.get("project_root", document.metadata.get("source_root", document.path.parent))).resolve()
    source_path = document.path.resolve().relative_to(source_root).as_posix()
    manifest["source_mod_id"] = document.metadata.get("source_mod_id")
    adapter = resource_adapter(adapter_id)
    for relative, content in rendered.items():
        output_keys = {entry.key for entry in adapter.parse_text(content, Path(relative)).entries}
        manifest["files"][relative] = {
            "source_path": source_path, "language": target_lang.get("code", ""),
            "source_hash": hashlib.sha256(document.source_text.encode("utf-8")).hexdigest(),
            "entries": [{"key": e.key, "source": e.value,
                         "needs_review": e.key in document.metadata.get("needs_review_keys", [])}
                        for e in document.entries if e.key in output_keys],
        }
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def _write_package(root: Path, contents: dict[str, str]) -> None:
    """Rollback the document's resources and provenance together on write failure."""
    paths = {name: safe_output(root, name) for name in contents}
    before = {name: path.read_bytes() if path.exists() else None for name, path in paths.items()}
    written = []
    try:
        for name, text in contents.items():
            written.append(name)
            atomic_write(paths[name], text)
    except BaseException:
        failures = []
        for name in reversed(written):
            try:
                if before[name] is None:
                    paths[name].unlink(missing_ok=True)
                else:
                    atomic_write(paths[name], before[name].decode("utf-8"))
            except Exception as exc:
                failures.append(f"{name}: {exc}")
        if failures:
            raise RuntimeError("Package write failed and rollback is incomplete: " + "; ".join(failures))
        raise


def rebuild(key_map: dict, translations: list[str], destination: str, target_lang: dict) -> str:
    first = next(iter(key_map.values()), None)
    if first is None or not isinstance(first.get("adapter_document"), Document):
        raise ValueError("Missing captured game resource document")
    outputs = write_document(first["adapter_document"], first["adapter_id"], translations,
                             destination, target_lang)
    if not outputs:
        raise ValueError("Adapter did not produce any localization resources")
    return outputs[0]
