"""Reference provenance stays separate from English authority and gold judgments."""
from types import SimpleNamespace

from .batch_repository import BatchConflict
from .batch_sources import freeze_sources
from .surviving_mars_csv import parse_text


async def freeze_reference(manager, project_id, file_ids):
    if not project_id and not file_ids:
        return None, {}
    if not project_id or not file_ids:
        raise BatchConflict("reference_selection_required", "Select both the reference project and source files.", 400)
    snapshot = await freeze_sources(manager, SimpleNamespace(project_id=project_id, file_ids=file_ids, source_column="Text"))
    if snapshot["adapter_id"] != "surviving_mars_csv":
        raise BatchConflict("reference_adapter_unsupported", "Reference tables currently use the Mars CSV contract.", 400)
    return snapshot, reference_table(snapshot)


def reference_table(snapshot):
    values, duplicates = {}, set()
    for file in snapshot["files"]:
        if not file["selected"]:
            continue
        doc = parse_text(file["content"])
        for row in doc.rows[doc.header_row_index + 1:]:
            if not row or not row[2].strip():
                continue
            if row[0] in values:
                duplicates.add(row[0])
            values[row[0]] = {"source": row[1], "translation": row[2], "file_id": file["file_id"], "sha256": file["sha256"]}
    for key in duplicates:
        values.pop(key, None)  # Do not silently select a duplicate global ID from different files.
    return values
