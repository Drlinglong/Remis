"""Read-only loader for the Issue #198 corpus/gold case manifest."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from scripts.developer_tools.archive_ab_contract import ArchiveCase, SourceEntry


SOURCE_ID = re.compile(r"^(?P<key>.+):(?P<version>\d+)$")


def parse_localisation_file(path: Path) -> dict[str, str]:
    """Parse the small Paradox localisation subset without re-encoding text."""

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(?P<key>[^:#][^:]*):(?P<version>\d+)\s+\"(?P<value>.*)\"\s*$", line)
        if not match:
            continue
        source_id = f"{match.group('key').strip()}:{match.group('version')}"
        value = match.group("value").replace(r"\n", "\n").replace(r'\"', '"').replace(r"\\", "\\")
        values[source_id] = value
    return values


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_archive_release(base_url: str, release_id: str) -> tuple[str, dict[str, Any]]:
    """Read a published Remis release through its localhost Agent API."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("archive API access is restricted to localhost")
    endpoint = f"{base_url.rstrip('/')}/api/agent/context/releases/{quote(release_id, safe='')}/effective"
    request = Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read()
    except OSError as exc:
        raise ValueError(f"could not read Remis archive release {release_id} from localhost API") from exc
    try:
        document = json.loads(raw.decode("utf-8"))
        release = document["release"]
        effective_context = document["effective_context"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"Remis archive API returned an invalid release payload: {release_id}") from exc
    if not isinstance(release, Mapping) or not isinstance(effective_context, Mapping):
        raise ValueError(f"Remis archive API returned an invalid release payload: {release_id}")
    metadata = {
        "source": "remis_agent_api",
        "artifact_path": endpoint,
        "artifact_sha256": _sha256_bytes(raw),
        "release_id": str(release.get("release_id") or release_id),
        "source_snapshot_hash": str(release.get("source_snapshot_hash") or ""),
        "created_at": str(release.get("created_at") or ""),
    }
    if not metadata["source_snapshot_hash"]:
        raise ValueError(f"Remis archive release has no source snapshot hash: {release_id}")
    return json.dumps(effective_context, ensure_ascii=False, sort_keys=True, separators=(",", ":")), metadata


def _sha256_bytes(value: bytes) -> str:
    import hashlib
    return hashlib.sha256(value).hexdigest()


def _archive_contexts(
    definition: Mapping[str, Any],
    *,
    archive_api_base_url: str | None,
    archive_release_id: str | None,
    archive_previous_release_id: str | None,
) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    """Resolve only published Remis releases; fixture prose cannot become B context."""
    if definition.get("archive_artifact_path"):
        raise ValueError("archive_artifact_path is unsupported; use a published Remis release via --archive-release-id")
    current_id = str(definition.get("archive_release_id") or archive_release_id or "")
    previous_id = str(definition.get("archive_previous_release_id") or archive_previous_release_id or "")
    if not current_id and not previous_id:
        return "", "", {}, {}
    if not archive_api_base_url:
        raise ValueError("archive release IDs require --archive-api-base-url")
    current = _load_archive_release(archive_api_base_url, current_id) if current_id else ("", {})
    previous = _load_archive_release(archive_api_base_url, previous_id) if previous_id else ("", {})
    return current[0], previous[0], current[1], previous[1]


def _selected_rows(gold: Mapping[str, Any], selector: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [row for row in gold.get("assignments", ()) if isinstance(row, Mapping)]
    chain_id = selector.get("chain_id")
    role = selector.get("content_role")
    prefix = selector.get("group_prefix")
    if chain_id:
        rows = [row for row in rows if chain_id in (row.get("chain_memberships") or ())]
    if role:
        rows = [row for row in rows if row.get("content_role") == role]
    if prefix:
        rows = [row for row in rows if str(row.get("group_key", "")).startswith(str(prefix))]
    return sorted(rows, key=lambda row: _unit_sort_key(str(row.get("unit_id", ""))))


def _unit_sort_key(unit_id: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", unit_id)
    return (int(match.group(1)) if match else 10**9, unit_id)


def _wiki_context(wiki_ids: tuple[str, ...], wiki_sources: list[Mapping[str, Any]]) -> str:
    """Render only the package's evaluator-facing facts into a prompt."""

    by_id = {str(item.get("evidence_id")): item for item in wiki_sources if isinstance(item, Mapping)}
    contexts: list[str] = []
    for evidence_id in wiki_ids:
        source = by_id.get(evidence_id)
        if not source:
            continue
        context_parts = [source.get("overall_mod_summary"), source.get("event_chain_summary")]
        context_parts.extend(source.get("trigger_contract", ()))
        structure = source.get("structure") or {}
        for event in structure.get("main_chain", ()):
            context_parts.append(_compact_event(event))
        for event in structure.get("quest_progression", ()):
            context_parts.append(_compact_event(event))
        for chain in structure.get("optional_chains", ()):
            context_parts.append(_compact_chain(chain))
        omega = structure.get("omega_alignment")
        if omega:
            context_parts.append(_compact_chain(omega))
        for event in structure.get("toxic_entity_events", ()):
            context_parts.append(_compact_event(event))
        context_parts.extend(source.get("translation_contract", ()))
        context = "\n".join(str(part) for part in context_parts if part)
        if context:
            contexts.append(f"[{source.get('page_title', evidence_id)}]\n{context}")
    return "\n\n".join(contexts)


def _compact_event(event: Mapping[str, Any]) -> str:
    title = str(event.get("title", "")).strip()
    if not title:
        title = f"Quest {event.get('quest', '')}".strip()
    details = [str(event[key]) for key in ("trigger", "theme", "causal_summary", "fact") if event.get(key)]
    details.extend(str(item) for key in ("branches", "outcomes", "motifs", "branching_notes") for item in event.get(key, ()))
    events = event.get("events")
    if events:
        details.append("Event order: " + " > ".join(str(item) for item in events))
    return f"{title}: " + " ".join(details)


def _compact_chain(chain: Mapping[str, Any]) -> str:
    title = str(chain.get("title", "Omega Alignment")).strip()
    details = [str(chain[key]) for key in ("availability", "summary", "building", "theme") if chain.get(key)]
    details.extend(str(item) for key in ("events", "prerequisites", "branches") for item in chain.get(key, ()))
    return f"{title}: " + " ".join(details)


def load_cases(
    manifest_path: Path,
    corpus_root: Path,
    *,
    archive_api_base_url: str | None = None,
    archive_release_id: str | None = None,
    archive_previous_release_id: str | None = None,
) -> tuple[list[ArchiveCase], dict[str, Any]]:
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases: list[ArchiveCase] = []
    wiki_path = manifest_path.parent / str(document.get("wiki_evidence_path", ""))
    wiki_document = json.loads(wiki_path.read_text(encoding="utf-8")) if wiki_path.exists() else {"sources": []}
    wiki_sources = wiki_document.get("sources", [])
    wiki_ids = {str(item.get("evidence_id")) for item in wiki_sources if isinstance(item, Mapping)}
    missing_wiki = set(document.get("wiki_sources", ())) - wiki_ids
    if missing_wiki:
        raise ValueError(f"fixture references missing Wiki evidence: {sorted(missing_wiki)}")
    provenance: dict[str, Any] = {
        "source_files": [],
        "gold_files": [],
        "wiki_sources": wiki_sources,
        "archive_artifacts": [],
        "wiki_package": {
            "schema_version": wiki_document.get("schema_version"),
            "package_version": wiki_document.get("package_version"),
            "accessed_on": wiki_document.get("accessed_on"),
        },
    }
    for definition in document.get("cases", ()):
        source_path = corpus_root / str(definition["source_path"])
        gold_path = corpus_root / str(definition["gold_path"])
        source_values = parse_localisation_file(source_path)
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        rows = _selected_rows(gold, definition["selection"])
        entries: list[SourceEntry] = []
        for row in rows:
            for source_id in row.get("item_keys", ()):
                match = SOURCE_ID.match(str(source_id))
                if not match or source_id not in source_values:
                    raise ValueError(f"gold/source mismatch for {definition['case_id']}: {source_id}")
                entries.append(SourceEntry(source_id, match.group("key"), int(match.group("version")), source_values[source_id], str(row["unit_id"]), str(row.get("group_key", ""))))
        case_kind = definition["case_kind"]
        persisted_archive_context, persisted_old_archive_context, archive_metadata, old_archive_metadata = _archive_contexts(
            definition,
            archive_api_base_url=archive_api_base_url,
            archive_release_id=archive_release_id,
            archive_previous_release_id=archive_previous_release_id,
        )
        wiki_evidence_ids = tuple(definition.get("wiki_evidence_ids", ()))
        cases.append(ArchiveCase(
            case_id=str(definition["case_id"]), dataset_id=str(definition["dataset_id"]), case_kind=case_kind,
            chain_id=str(definition["selection"].get("chain_id")) if case_kind == "event_chain" else None,
            reference_batch_id=str(definition["reference_batch_id"]) if case_kind == "reference_batch" else None,
            source_entries=tuple(entries), gold_facts=tuple(definition.get("gold_facts", ())),
            wiki_evidence_ids=wiki_evidence_ids, wiki_context=_wiki_context(wiki_evidence_ids, wiki_sources),
            chunk_index=int(definition.get("chunk_index", 0)),
            chunk_count=int(definition.get("chunk_count", 1)), chunk_reason=str(definition.get("chunk_reason", "not_chunked")),
            adjacent_source_text=tuple(definition.get("adjacent_source_text", ())), glossary=dict(definition.get("glossary", {})),
            mod_summary=str(definition.get("mod_summary", "")), matched_chain_context=str(definition.get("matched_chain_context", "")),
            old_mod_summary=str(definition.get("old_mod_summary", "")),
            persisted_archive_context=persisted_archive_context,
            persisted_old_archive_context=persisted_old_archive_context,
            persisted_archive_metadata=archive_metadata,
            persisted_old_archive_metadata=old_archive_metadata,
        ))
        provenance["archive_artifacts"].append({
            "case_id": str(definition["case_id"]),
            "current": archive_metadata,
            "previous": old_archive_metadata,
        })
        source_hash = _sha256(source_path)
        expected_hash = str((gold.get("fixture") or {}).get("sha256") or "")
        if expected_hash and source_hash != expected_hash:
            raise ValueError(f"source hash disagrees with immutable gold metadata: {source_path}")
        provenance["source_files"].append({"path": str(definition["source_path"]), "sha256": source_hash, "bytes": source_path.stat().st_size})
        provenance["gold_files"].append({"path": str(definition["gold_path"]), "sha256": _sha256(gold_path), "dataset_version": gold.get("dataset_version"), "schema_version": gold.get("schema_version"), "source_gold_sha256": (gold.get("provenance") or {}).get("source_gold_sha256")})
    return cases, provenance


__all__ = ["load_cases", "parse_localisation_file"]
