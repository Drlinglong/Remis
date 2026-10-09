"""Coverage imports add evidence without erasing pending translation work."""
import json


def append_unique(existing, incoming):
    result, seen = [], set()
    for item in [*existing, *incoming]:
        value = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def merge_pending_evidence(current, incoming):
    for field in ("context_snippets", "context_evidence", "source_files", "suggestion_variants"):
        setattr(current, field, append_unique(getattr(current, field), getattr(incoming, field)))
    current.source_file = current.source_file or incoming.source_file
    for field in ("suggestion", "reasoning"):
        if not getattr(current, field):
            setattr(current, field, getattr(incoming, field))
    for field in ("frequency", "local_unit_coverage", "mention_count"):
        setattr(current, field, max(getattr(current, field), getattr(incoming, field)))
    # Confidence and tier belong to the retained suggestion, not the fresh scan.
