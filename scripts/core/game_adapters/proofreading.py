"""Resource proofreading inside the existing archive-backed edit workflow."""
from pathlib import Path
import hashlib

from .output_records import output_record
from .registry import resource_adapter
from .workflow_bridge import atomic_write, safe_output


def _binding(project, target, adapter):
    package_root, record = output_record(target)
    source_root = Path(project["source_path"])
    if record:
        source = safe_output(source_root, record["source_path"])
        return source, record["language"], {e["key"]: e["source"] for e in record["entries"]}
    target_document = adapter.parse(Path(target))
    target_keys = {entry.key for entry in target_document.entries}
    discovery = adapter.discover(source_root, {"code": project.get("source_language", "en")})
    matches = []
    for resource in discovery.resources:
        document = adapter.parse(resource.path, resource.metadata)
        values = {entry.key: entry.value for entry in document.entries}
        if target_keys and target_keys.issubset(values):
            matches.append((resource.path, values))
    if len(matches) != 1:
        raise ValueError("Source resource cannot be matched uniquely; select the correct source Mod")
    from scripts.app_settings import LANGUAGES
    languages = [lang["code"] for lang in LANGUAGES.values()
                 if adapter.language_folder(lang).casefold() in [part.casefold() for part in Path(target).parts]]
    if len(languages) != 1:
        raise ValueError("Target resource language cannot be resolved uniquely")
    return matches[0][0], languages[0], matches[0][1]


async def get_proofread_data(service, project, target_file_path, file_id):
    adapter = resource_adapter(project["game_id"])
    target = Path(target_file_path)
    document = adapter.parse(target)
    _, language, source = _binding(project, target, adapter)
    _, record = output_record(target)
    pending = {entry["key"] for entry in record.get("entries", []) if entry.get("needs_review")}
    rows = [{"entry_id": f"entry-{index}", "row_type": "translation",
             "line_number": entry.line_number, "key": entry.key,
             "source_value": source.get(entry.key, ""), "ai_value": entry.value,
             "final_value": entry.value, "editable": entry.key in source,
             "issues": ([{"code": "source_changed_review_required", "severity": "warning"}]
                        if entry.key in pending else []) + [d.as_dict() for d in adapter.validate(source.get(entry.key, ""), entry.value)]}
            for index, entry in enumerate(document.entries)]
    return {"file_id": file_id, "file_path": str(target), "mod_name": project.get("name", ""),
            "target_language": language, "rows": rows,
            "entries": [{"key": r["key"], "original": r["source_value"],
                         "translation": r["final_value"], "line_number": r["line_number"]} for r in rows],
            "file_content": document.source_text, "ai_content": document.source_text,
            "final_content": document.source_text,
            "document_revision": hashlib.sha256(target.read_bytes()).hexdigest()}


async def save_proofread_data(service, project, target_file_path, file_id,
                              entries_list, structure_patches=None):
    if structure_patches:
        raise ValueError("Game resource structure is preserved; edit translation values only")
    adapter = resource_adapter(project["game_id"])
    target = Path(target_file_path)
    discovery = adapter.discover(Path(project["source_path"]), {"code": project.get("source_language", "en")})
    if target.resolve() in {resource.path.resolve() for resource in discovery.resources}:
        raise ValueError("Source resources are read-only; edit a translation package")
    document = adapter.parse(target)
    source_file, language, source = _binding(project, target, adapter)
    values = {entry.key: entry.value for entry in document.entries}
    submitted = [str(entry.get("key", "")) for entry in entries_list]
    if len(submitted) != len(set(submitted)) or not set(submitted).issubset(values):
        raise ValueError("Unknown or duplicate proofreading keys")
    for entry in entries_list:
        key, value = entry["key"], str(entry["translation"])
        if key not in source or any(d.severity == "error" for d in adapter.validate(source[key], value)):
            raise ValueError(f"Invalid translation tokens or missing source: {key}")
        values[key] = value
    rendered = adapter.render(document, values, {"code": language})
    if len(rendered) != 1:
        raise ValueError("Proofreading must address exactly one target resource")
    rewritten = next(iter(rendered.values()))
    atomic_write(target, rewritten)
    try:
        count = service.archive_manager.update_translations(
            project.get("name", ""), source_file.resolve().relative_to(Path(project["source_path"]).resolve()).as_posix(), entries_list, language,
            project_id=project.get("project_id"))
        if count != len(entries_list):
            raise RuntimeError("Proofreading archive did not persist every submitted entry")
    except Exception:
        atomic_write(target, document.source_text)
        raise
    from .review_state import acknowledge
    acknowledge(target, submitted)
    await service.project_manager.update_file_status_with_kanban_sync(project["project_id"], file_id, "done")
    return {"status": "success", "document_revision": hashlib.sha256(target.read_bytes()).hexdigest()}
