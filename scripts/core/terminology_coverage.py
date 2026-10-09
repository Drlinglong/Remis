"""Deterministic coverage evidence, not automatic semantic approval."""
from collections import Counter, defaultdict
import json
import re

from .batch_artifacts import fingerprint
from scripts.core.neologism_extraction import SourceEvidence
from scripts.schemas.context_candidate import normalized_match_key

NAME_FIELDS = {"displayname", "display_name", "display_name_pl", "display_name_twolines", "name", "title_text"}


def plural_form(singular):
    singular = singular.casefold()
    if singular.endswith("y") and len(singular) > 1 and singular[-2] not in "aeiou":
        plural = singular[:-1] + "ies"
    elif singular.endswith(("s", "x", "z", "ch", "sh")):
        plural = singular + "es"
    else:
        plural = singular + "s"
    return plural


def object_identity(entry):
    context = entry.get("context", "").split(" ", 1)[-1]
    if context.startswith("{"):
        try:
            context = json.loads(context).get("object_context", "")
        except ValueError:
            return None
    parts = context.split()
    if len(parts) >= 3 and parts[-1].lower() in NAME_FIELDS:
        return {"kind": parts[0], "object": " ".join(parts[1:-1]), "field": parts[-1]}
    # Other adapters can expose conventional name keys without a Mars Context column.
    if re.search(r"(?:^|_)(?:name|title)$", entry["key"], re.I):
        return {"kind": "localization_key", "object": entry["key"], "field": "name_key"}
    return None


def occurrence_evidence(entries, spellings, example_limit):
    spellings = sorted(set(spellings), key=lambda value: (-len(value), value.casefold()))
    if not spellings:
        return {}, {}
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(s) for s in spellings) + r")(?!\w)", re.I)
    counts, examples = Counter(), defaultdict(list)
    for entry in entries:
        # Count source entries, not repeated occurrences inside the same paragraph.
        matched = {match.group(0).casefold() for match in pattern.finditer(entry["source"])}
        for spelling in matched:
            counts[spelling] += 1
            if len(examples[spelling]) < example_limit:
                examples[spelling].append({"source_id": entry["key"], "entry_id": entry["id"],
                    "context": entry["context"], "source": entry["source"]})
    return dict(counts), dict(examples)


def scan_coverage(snapshot, glossary_rows, reference, minimum=3, example_limit=3):
    entries = [e for f in snapshot["files"] if f["selected"] for e in f["entries"]]
    known_spellings, known_ids = defaultdict(list), {}
    for row in glossary_rows:
        metadata = row.get("raw_metadata") or {}
        detail = metadata.get("terminology") or {}
        if detail.get("review_state") in {"pending", "rejected"}:
            continue
        concept = detail.get("concept_id", row["entry_id"])
        source = metadata.get("source_text") or row["translations"].get("en", "")
        known_ids[detail.get("source_id", "")] = concept
        for spelling in [source, *row.get("variants", {}).get("en", [])]:
            if spelling:
                known_spellings[spelling.casefold()].append(concept)
    plural_map = defaultdict(set)
    for spelling, concepts in known_spellings.items():
        plural_map[plural_form(spelling)].update(concepts)
    seeds = []
    for entry in entries:
        identity = object_identity(entry)
        if not identity and entry["key"] not in known_ids:
            # Observed short plural labels can supply evidence; do not invent an unobserved alias.
            if entry["source"].casefold() not in plural_map:
                continue
            identity = {"kind": "observed_plural_label", "object": entry["key"], "field": "observed_plural"}
        text = entry["source"]
        if "<" in text or "\n" in text or not text.strip() or len(text) > 200:
            continue
        identity = identity or {"kind": "existing_source_id", "object": entry["key"], "field": "source_id"}
        seeds.append((entry, identity))
    counts, examples = occurrence_evidence(entries, [e["source"] for e, _ in seeds] + list(known_spellings), example_limit)
    objects = defaultdict(list)
    for entry, identity in seeds:
        objects[(identity["kind"], identity["object"])].append(entry)
    candidates, alias_gaps = [], []
    seen = set()
    for entry, identity in seeds:
        spelling = entry["source"].casefold()
        key = (identity["kind"], identity["object"], spelling)
        if key in seen:
            continue
        seen.add(key)
        concepts = set(known_spellings.get(spelling, []))
        same_object = objects[(identity["kind"], identity["object"])]
        anchors = set().union(*(set(known_spellings.get(e["source"].casefold(), [])) for e in same_object))
        anchors.update(known_ids[e["key"]] for e in same_object if e["key"] in known_ids)
        plural_anchors = plural_map.get(spelling, set())
        verified_anchors = anchors & plural_anchors
        alias_anchors = verified_anchors or (plural_anchors if identity["kind"] == "observed_plural_label" else set())
        if not concepts and len(alias_anchors) == 1:
            alias_gaps.append({"source": entry["source"], "concept_id": next(iter(alias_anchors)),
                "source_id": entry["key"], "object_identity": identity,
                "confidence": "high" if verified_anchors else "medium",
                "basis": "observed inflection; same object confirmed" if verified_anchors else "observed plural; sense still requires review"})
        ref = reference.get(entry["key"])
        item = {"candidate_id": "tc_" + fingerprint(key)[:24], "source": entry["source"],
            "source_id": entry["key"], "object_identity": identity,
            "official_sc": ref["translation"] if ref and ref["source"] == entry["source"] else None,
            "source_entry_count": counts.get(spelling, 0), "examples": examples.get(spelling, []),
            "matched_concept_ids": sorted(concepts), "status": "covered" if concepts else "uncovered",
            "priority": "high" if counts.get(spelling, 0) >= minimum else "low",
            "archive_normalized_key": normalized_match_key(entry["source"], snapshot["source_locale"]),
            "archive_evidence": [SourceEvidence(source_item_id=e["entry_id"], item_key=e["source_id"],
                snippet=e["source"][:2000]).model_dump(mode="json") for e in examples.get(spelling, [])],
            "semantic_approval": False}
        candidates.append(item)
    # Explicitly distinguish spelling coverage from concept disambiguation.
    return {"schema": "terminology-coverage/2", "entry_count": len(entries), "candidates": candidates,
        "candidate_count": len(candidates), "uncovered_count": sum(c["status"] == "uncovered" for c in candidates),
        "high_priority_uncovered_count": sum(c["status"] == "uncovered" and c["priority"] == "high" for c in candidates),
        "alias_gaps": alias_gaps, "coverage_is_lexical_not_semantic": True,
        "occurrence_policy": "source entries; longest spelling wins within overlapping spans",
        "limitations": ["Names without structured context or known source ID may be missed.",
                        "Lexical matches do not prove the correct concept sense.",
                        "Candidate and alias suggestions never modify a glossary automatically."]}
