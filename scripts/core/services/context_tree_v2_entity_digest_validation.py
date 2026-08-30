"""Normalization and response-validation rules for the v2 entity digest."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ValidationError

from scripts.schemas.context_tree_v2_entity_digest import (
    CandidateGrade,
    CandidateKind,
    DigestCandidate,
    DigestLocalUnit,
    EntityDigest,
    EntityDigestDiagnostic,
    EntityDigestResponse,
    EntityEvidenceBundle,
    EntityEvidenceRecord,
    SamplingResult,
    SemanticMergeProposal,
    SemanticMergeRecompute,
)


def read_value(raw: Any, *names: str, default: Any = None) -> Any:
    if isinstance(raw, Mapping):
        for name in names:
            if name in raw:
                return raw[name]
        return default
    for name in names:
        if hasattr(raw, name):
            return getattr(raw, name)
    return default


def enum_value(raw: Any) -> Any:
    return getattr(raw, "value", raw)


def strings(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    values = (raw,) if isinstance(raw, str) else raw
    try:
        values = tuple(values)
    except TypeError:
        values = (values,)
    return tuple(dict.fromkeys(
        str(enum_value(item)).strip()
        for item in values
        if str(enum_value(item)).strip()
    ))


def grade_for_units(count: int) -> CandidateGrade:
    if count >= 3:
        return CandidateGrade.A
    if count == 2:
        return CandidateGrade.B
    return CandidateGrade.C


def normalize_candidate(raw: Any) -> DigestCandidate:
    if isinstance(raw, DigestCandidate):
        return raw
    source = raw.model_dump(mode="python") if isinstance(raw, DigestCandidate) else raw
    unit_ids = strings(read_value(source, "local_unit_ids", "unit_ids", default=()))
    incoming_grade = enum_value(read_value(source, "grade", "automatic_grade", default=None))
    automatic_grade = grade_for_units(len(unit_ids)).value
    manual = enum_value(read_value(source, "manual_grade_override", default=None))
    grade_source = str(read_value(source, "grade_source", default="automatic") or "automatic")
    if manual not in {None, *[item.value for item in CandidateGrade]}:
        manual = None
    if manual is None and grade_source == "manual" and incoming_grade in {
        item.value for item in CandidateGrade
    }:
        manual = incoming_grade
    governed_grade = read_value(source, "automatic_grade", default=None) is not None or any(
        read_value(source, name, default=None) is not None
        for name in ("grade_source", "manual_grade_override")
    )
    grade = manual or automatic_grade if governed_grade else (
        incoming_grade if incoming_grade in {item.value for item in CandidateGrade} else automatic_grade
    )
    descriptions = strings(read_value(source, "local_descriptions", default=()))
    description = str(read_value(source, "local_description", "description", default="") or "")
    if description and description not in descriptions:
        descriptions = (description, *descriptions)
    description = " ; ".join(descriptions)[:2_000]
    return DigestCandidate.model_validate({
        "candidate_id": read_value(source, "candidate_id", "id"),
        "compact_name": read_value(source, "compact_name", "canonical_name", "name"),
        "local_description": description,
        "aliases": strings(read_value(source, "aliases", "alias_candidates", default=())),
        "local_unit_ids": unit_ids,
        "event_group_ids": strings(read_value(source, "event_group_ids", "event_groups", default=())),
        "grade": grade,
        "kind": enum_value(read_value(source, "kind", "candidate_kind", default="entity")),
        "grade_source": "manual" if manual else "automatic",
        "manual_grade_override": manual,
    })


def normalize_unit(raw: Any, position: int) -> DigestLocalUnit:
    text = read_value(raw, "source_text", "text", "original_text", default=None)
    if text is None:
        entries = read_value(raw, "entries", "items", default=()) or ()
        text = "\n".join(
            str(read_value(item, "source_text", "text", "original_text", default=""))
            for item in entries
        )
    order = read_value(raw, "unit_order", "order", "source_order", default=position)
    try:
        order = int(order)
    except (TypeError, ValueError):
        order = position
    top_description = str(read_value(raw, "fragment_summary", "summary", "local_summary", default="") or "")
    descriptions = strings(read_value(raw, "local_descriptions", "descriptions", default=()))
    entries = read_value(raw, "entries", "items", default=()) or ()
    entry_descriptions = strings(
        read_value(item, "local_description", "description", "summary", default="")
        for item in entries
    )
    descriptions = tuple(dict.fromkeys((
        *(item for item in (top_description,) if item.strip()),
        *descriptions,
        *entry_descriptions,
    )))
    return DigestLocalUnit.model_validate({
        "unit_id": read_value(raw, "unit_id", "local_unit_id", "id"),
        "source_text": str(text or ""),
        "event_group_ids": strings(read_value(raw, "event_group_ids", "event_group_id", "group_id", default=())),
        "batch_index": read_value(raw, "batch_index", "batch", default=None),
        "unit_order": order,
        "fragment_summary": " ; ".join(descriptions)[:2_000],
        "local_descriptions": descriptions,
    })


def normalize_candidates(values: Sequence[Any]) -> tuple[list[DigestCandidate], list[EntityDigestDiagnostic]]:
    candidates, diagnostics = _normalize(values, normalize_candidate, "invalid_candidate_skipped")
    grouped: dict[str, list[DigestCandidate]] = {}
    order: list[str] = []
    for candidate in candidates:
        if candidate.candidate_id not in grouped:
            order.append(candidate.candidate_id)
        grouped.setdefault(candidate.candidate_id, []).append(candidate)
    merged: list[DigestCandidate] = []
    for candidate_id in order:
        items = grouped[candidate_id]
        if len(items) == 1:
            merged.append(items[0])
        else:
            merged.append(_merge_candidates(items))
            diagnostics.append(diagnostic(
                "duplicate_candidate_aggregated",
                candidate_id,
                "Merged repeated normalized candidate evidence across extraction batches.",
            ))
    return merged, diagnostics


def normalize_units(values: Sequence[Any]) -> tuple[list[DigestLocalUnit], list[EntityDigestDiagnostic]]:
    return _normalize(values, normalize_unit, "invalid_local_unit_skipped")


def build_evidence_bundle(
    candidate: DigestCandidate,
    units: Mapping[str, DigestLocalUnit],
) -> tuple[EntityEvidenceBundle, list[EntityDigestDiagnostic]]:
    """Retain every #2 unit and mark only sampled units as included later."""

    diagnostics: list[EntityDigestDiagnostic] = []
    records: list[EntityEvidenceRecord] = []
    descriptions: list[str] = []
    if candidate.local_description.strip():
        descriptions.append(candidate.local_description.strip())
    for unit_id in candidate.local_unit_ids:
        unit = units.get(unit_id)
        if unit is None:
            diagnostics.append(diagnostic(
                "candidate_evidence_unit_not_found",
                candidate.candidate_id,
                f"Retained an empty evidence record for unknown local unit {unit_id!r}.",
            ))
            records.append(EntityEvidenceRecord(
                unit_id=unit_id,
                local_description=candidate.local_description,
                local_descriptions=(candidate.local_description,) if candidate.local_description else (),
            ))
            continue
        local_descriptions = tuple(dict.fromkeys(
            item.strip()
            for item in (unit.local_descriptions or (unit.fragment_summary,))
            if item and item.strip()
        ))
        descriptions.extend(local_descriptions)
        records.append(EntityEvidenceRecord(
            unit_id=unit.unit_id,
            source_text=unit.source_text,
            local_description=" ; ".join(local_descriptions),
            local_descriptions=local_descriptions,
            event_group_ids=unit.event_group_ids,
        ))
    mechanical = "\n".join(dict.fromkeys(item for item in descriptions if item))
    return EntityEvidenceBundle(
        candidate_id=candidate.candidate_id,
        full_evidence=tuple(records),
        mechanical_local_description=mechanical,
    ), diagnostics


def _merge_candidates(items: Sequence[DigestCandidate]) -> DigestCandidate:
    first = items[0]
    aliases = tuple(dict.fromkeys(alias for item in items for alias in item.aliases))
    unit_ids = tuple(dict.fromkeys(unit_id for item in items for unit_id in item.local_unit_ids))
    group_ids = tuple(dict.fromkeys(group_id for item in items for group_id in item.event_group_ids))
    descriptions = tuple(dict.fromkeys(
        description.strip()
        for item in items
        for description in (item.local_description,)
        if description.strip()
    ))
    manual = next((item.manual_grade_override for item in items if item.manual_grade_override is not None), None)
    automatic = grade_for_units(len(unit_ids))
    return first.model_copy(update={
        "aliases": aliases[:100],
        "local_unit_ids": unit_ids[:1_000],
        "event_group_ids": group_ids[:500],
        "local_description": " ; ".join(descriptions)[:2_000],
        "kind": CandidateKind.ENTITY if any(item.kind is CandidateKind.ENTITY for item in items) else CandidateKind.TERM,
        "grade": manual or automatic,
        "grade_source": "manual" if manual else "automatic",
        "manual_grade_override": manual,
    })


def _normalize(values: Sequence[Any], converter: Any, code: str) -> tuple[list[Any], list[EntityDigestDiagnostic]]:
    result: list[Any] = []
    diagnostics: list[EntityDigestDiagnostic] = []
    seen: set[str] = set()
    for index, raw in enumerate(values):
        try:
            item = converter(raw, index) if converter is normalize_unit else converter(raw)
        except (ValidationError, TypeError, ValueError) as error:
            diagnostics.append(diagnostic(code, detail=f"index {index}: {str(error)[:240]}"))
            continue
        identity = item.candidate_id if isinstance(item, DigestCandidate) else item.unit_id
        if identity in seen:
            diagnostics.append(diagnostic("duplicate_id_skipped", detail=f"Duplicate ID {identity!r} was dropped."))
            continue
        seen.add(identity)
        result.append(item)
    return result, diagnostics


def group_records(groups: Any) -> Mapping[str, Any] | Sequence[Mapping[str, Any]] | None:
    if groups is None or isinstance(groups, Mapping):
        if isinstance(groups, Mapping):
            return {
                str(key): read_value(value, "summary", "description", "text", default=value)
                for key, value in groups.items()
            }
        return None
    return [
        {
            "group_id": read_value(group, "group_id", "event_group_id", "id", default=f"group_{index}"),
            "summary": read_value(group, "summary", "description", "text", default=""),
        }
        for index, group in enumerate(groups)
    ]


def parse_digest_response(
    raw: Any,
    *,
    max_evidence_units: int,
) -> tuple[EntityDigestResponse, dict[str, Any], list[EntityDigestDiagnostic]]:
    if isinstance(raw, BaseModel):
        payload = raw.model_dump(mode="json")
    elif isinstance(raw, str):
        payload = json.loads(raw)
    elif isinstance(raw, Mapping):
        payload = dict(raw)
    else:
        payload = None
    if not isinstance(payload, dict):
        raise TypeError("Digest response must be a JSON object, mapping, or Pydantic model.")
    diagnostics: list[EntityDigestDiagnostic] = []
    if "semantic_merge" not in payload and (
        "semantic_merge_target_id" in payload or "semantic_merge_member_ids" in payload
    ):
        payload["semantic_merge"] = {
            "target_candidate_id": payload.pop("semantic_merge_target_id", None),
            "member_candidate_ids": payload.pop("semantic_merge_member_ids", ()),
        }
    evidence = payload.get("evidence_unit_ids", ())
    if isinstance(evidence, (list, tuple)) and len(evidence) > max_evidence_units:
        diagnostics.append(diagnostic(
            "evidence_unit_budget_exceeded",
            detail=f"Only the first {max_evidence_units} evidence IDs are considered.",
        ))
        payload["evidence_unit_ids"] = list(evidence[:max_evidence_units])
    return EntityDigestResponse.model_validate(payload), payload, diagnostics


def accept_digest_response(
    response: EntityDigestResponse,
    focus: DigestCandidate,
    sampling: SamplingResult,
    candidates: Mapping[str, DigestCandidate],
    units: Mapping[str, DigestLocalUnit],
    evidence_bundle: EntityEvidenceBundle,
    diagnostics: list[EntityDigestDiagnostic],
    digest_segment_id: str | None = None,
) -> EntityDigest | None:
    if response.candidate_id != focus.candidate_id:
        diagnostics.append(diagnostic(
            "response_candidate_id_mismatch",
            focus.candidate_id,
            f"Expected {focus.candidate_id!r}, got {response.candidate_id!r}.",
        ))
        return None
    sampled = {unit.unit_id for unit in sampling.units}
    evidence: list[str] = []
    for unit_id in response.evidence_unit_ids:
        if unit_id not in units:
            diagnostics.append(diagnostic("unknown_evidence_unit_dropped", focus.candidate_id, f"Dropped unknown unit {unit_id!r}."))
        elif unit_id not in sampled:
            diagnostics.append(diagnostic("unsampled_evidence_unit_dropped", focus.candidate_id, f"Dropped unseen unit {unit_id!r}."))
        elif unit_id not in evidence:
            evidence.append(unit_id)
    merge = validate_semantic_merge(response.semantic_merge, focus, candidates, diagnostics)
    included = set(sampled)
    full_evidence = tuple(
        record.model_copy(update={
            "included_in_digest": record.unit_id in included,
            "digest_segment_id": digest_segment_id if record.unit_id in included else None,
            "digest_segment_ids": (digest_segment_id,) if digest_segment_id and record.unit_id in included else (),
        })
        for record in evidence_bundle.full_evidence
    )
    return EntityDigest(
        candidate_id=focus.candidate_id,
        summary=response.summary,
        llm_digest=response.summary,
        mechanical_local_description=evidence_bundle.mechanical_local_description,
        full_evidence=full_evidence,
        evidence_unit_ids=tuple(evidence),
        semantic_merge=merge,
        sampling=sampling.metadata,
    )


def validate_semantic_merge(
    merge: SemanticMergeProposal | None,
    focus: DigestCandidate,
    candidates: Mapping[str, DigestCandidate],
    diagnostics: list[EntityDigestDiagnostic],
) -> SemanticMergeProposal | None:
    if merge is None:
        return None
    if merge.target_candidate_id not in candidates:
        diagnostics.append(diagnostic("unknown_semantic_merge_target_dropped", focus.candidate_id, f"Dropped target {merge.target_candidate_id!r}."))
        return None
    members = [item for item in merge.member_candidate_ids if item in candidates]
    for item in merge.member_candidate_ids:
        if item not in candidates:
            diagnostics.append(diagnostic("unknown_semantic_merge_member_dropped", focus.candidate_id, f"Dropped member {item!r}."))
    if any(candidates[item].kind is not CandidateKind.ENTITY for item in members):
        diagnostics.append(diagnostic("non_entity_semantic_merge_dropped", focus.candidate_id, "Semantic merge may contain only entity candidates."))
        return None
    members = list(dict.fromkeys(members))
    if focus.candidate_id not in members:
        diagnostics.append(diagnostic("semantic_merge_focus_missing", focus.candidate_id, "Dropped merge without the focused candidate."))
        return None
    if merge.target_candidate_id not in members:
        diagnostics.append(diagnostic("semantic_merge_target_missing_from_members", focus.candidate_id, "Dropped merge whose target was not a member."))
        return None
    return SemanticMergeProposal(
        target_candidate_id=merge.target_candidate_id,
        member_candidate_ids=tuple(members),
        reason=merge.reason,
    )


def recompute_semantic_merges(
    digests: Sequence[EntityDigest],
    candidates: Mapping[str, DigestCandidate],
    positions: Mapping[str, int],
) -> list[SemanticMergeRecompute]:
    result: list[SemanticMergeRecompute] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for digest in digests:
        merge = digest.semantic_merge
        if merge is None:
            continue
        key = (merge.target_candidate_id, tuple(sorted(merge.member_candidate_ids)))
        if key in seen:
            continue
        seen.add(key)
        members = [candidates[item] for item in merge.member_candidate_ids if item in candidates]
        unit_ids = sorted(
            {unit_id for member in members for unit_id in member.local_unit_ids},
            key=lambda item: positions.get(item, 10**9),
        )
        group_ids = sorted({group_id for member in members for group_id in member.event_group_ids})
        result.append(SemanticMergeRecompute(
            target_candidate_id=merge.target_candidate_id,
            member_candidate_ids=merge.member_candidate_ids,
            source_candidate_id=digest.candidate_id,
            merged_local_unit_ids=tuple(unit_ids),
            merged_event_group_ids=tuple(group_ids),
            local_unit_coverage=len(unit_ids),
            recomputed_grade=grade_for_units(len(unit_ids)),
        ))
    return result


def diagnostic(
    code: str,
    candidate_id: str | None = None,
    detail: str = "",
) -> EntityDigestDiagnostic:
    return EntityDigestDiagnostic(code=code, candidate_id=candidate_id, detail=detail)
