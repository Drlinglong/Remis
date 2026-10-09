"""Public terminology snapshots over the existing editable glossary.

Only export schema fields; local evidence paths and database ownership never
become release resources. This module does not persist or modify glossary data.
"""
from copy import deepcopy
import re

from .batch_artifacts import fingerprint
from .batch_repository import BatchConflict
from .glossary_terminology_review import review_basis
from scripts.schemas.glossary_terminology import ReviewedGlossaryTerm


def public_description(value):
    path = r'(?:[A-Za-z]:[\\/]|\\\\)[^\r\n"<>|]*?\.(?:csv|lua|jsonl?|fpk|hpk|sqlite|py|md)(?::\d+)?'
    return re.sub(path, lambda match: match.group().replace("\\", "/").rsplit("/", 1)[-1], value)


def public_term(row, term, locale):
    detail = row["raw_metadata"].get("terminology", {})
    payload = term.model_dump()
    # Evidence remains traceable by digest / ID without exposing local paths.
    evidence_fields = {"sha256", "source_sha256", "record_id", "source_id", "id",
                       "role", "source_kind", "workshop_id", "match_status"}
    payload["evidence_refs"] = [
        {key: value for key, value in evidence.items() if key in evidence_fields}
        for evidence in payload["evidence_refs"] if isinstance(evidence, dict)
    ]
    payload["evidence_refs"] = [item for item in payload["evidence_refs"] if item]
    for key in ("review_state", "confidence", "source_id", "original_candidate",
                "audit_reason", "audit_suggestion"):
        if key in detail:
            payload[key] = deepcopy(detail[key])
    for key in ("sense", "audit_reason", "reviewer"):
        if key in payload:
            payload[key] = public_description(payload[key])
    state = payload.get("review_state", "candidate")
    if state in {"reviewed", "approved"} and (
        detail.get("review_basis") != review_basis(term.source, term.translation, detail)
        or ("alias_review_basis" in detail and detail["alias_review_basis"] != term.aliases)
    ):
        payload["review_state"] = "candidate"
    payload["reference_translations"] = {
        key: value for key, value in row["translations"].items()
        if key in {"en", "zh-CN", "zh-TW"} and key != locale
    }
    # Human/model review provenance is expressed by review_state/dimensions;
    # the historical reference is already represented in public evidence IDs.
    return ReviewedGlossaryTerm.model_validate(payload).model_dump(exclude_none=True)


def distribution_snapshot(glossary, rows, terms, preview, expected_fingerprint):
    if preview["fingerprint"] != expected_fingerprint:
        raise BatchConflict("glossary_changed", "Inspect the glossary before exporting a distribution snapshot.")
    by_concept = {term.concept_id: term for term in terms}
    exported = []
    for row in rows:
        detail = row["raw_metadata"].get("terminology", {})
        concept = detail.get("concept_id", f"glossary:{row['glossary_id']}:{row['entry_id']}")
        if concept in by_concept:
            exported.append(public_term(row, by_concept[concept], preview["locale"]))
    exported.sort(key=lambda item: item["concept_id"])
    snapshot = {key: deepcopy(preview[key]) for key in (
        "game_id", "locale", "fingerprint", "entry_count", "eligible_count", "review_states")}
    snapshot["excluded"] = [{"reason": item["reason"]} for item in preview["excluded"]]
    digest = fingerprint(exported)
    return {
        "schema_version": "remis-glossary-distribution/1",
        "snapshot": snapshot,
        "import_payload": {
            "game_id": glossary["game_id"], "locale": preview["locale"],
            "name": glossary["name"], "description": glossary.get("description") or "",
            "import_key": f"distribution:{glossary['game_id']}:{preview['locale']}:{digest}",
            "terms": exported, "approved": False,
        },
    }
