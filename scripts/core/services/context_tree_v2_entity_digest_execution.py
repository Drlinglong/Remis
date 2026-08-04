"""Bounded multi-segment execution engine for v2 entity digests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from scripts.core.prompts.context_tree_v2_entity_digest_prompt import (
    ENTITY_DIGEST_SCHEMA_NAME,
    build_entity_digest_messages,
)
from scripts.core.services.context_tree_v2_entity_digest_selection import (
    build_program_project_overview,
    sample_entity_units,
    segment_entity_units,
)
from scripts.core.services.context_tree_v2_entity_digest_validation import (
    accept_digest_response,
    build_evidence_bundle,
    diagnostic,
    group_records,
    normalize_candidates,
    normalize_units,
    parse_digest_response,
    recompute_semantic_merges,
    validate_semantic_merge,
)
from scripts.schemas.context_tree_v2_entity_digest import (
    CandidateGrade,
    CandidateKind,
    DigestCandidate,
    DigestLocalUnit,
    EntityDigest,
    EntityDigestCallRecord,
    EntityDigestDiagnostic,
    EntityDigestResponse,
    EntityDigestRunResult,
    EntityEvidenceBundle,
    MAX_ENTITY_SOURCE_CHARS,
    MAX_ENTITY_UNITS,
    MAX_PROJECT_OVERVIEW_CHARS,
    PartialEntityDigest,
    ProjectOverview,
    SampledLocalUnit,
    SamplingMetadata,
    SamplingResult,
)
MAX_DIGEST_CATALOG_ITEMS = 120
MAX_DIGEST_CATALOG_NAME_CHARS = 160
MAX_DIGEST_CATALOG_DESCRIPTION_CHARS = 240
class EntityDigestExecutionEngine:
    """Execute short entities once and long entities by partials plus reduction."""

    def __init__(
        self,
        handler: Any,
        *,
        max_units: int = MAX_ENTITY_UNITS,
        max_source_chars: int = MAX_ENTITY_SOURCE_CHARS,
        max_project_overview_chars: int = MAX_PROJECT_OVERVIEW_CHARS,
    ) -> None:
        if not 1 <= max_units <= MAX_ENTITY_UNITS:
            raise ValueError("digest unit budget exceeds the v2 safety limit")
        if not 1 <= max_source_chars <= MAX_ENTITY_SOURCE_CHARS:
            raise ValueError("digest source budget exceeds the v2 safety limit")
        if not 1 <= max_project_overview_chars <= MAX_PROJECT_OVERVIEW_CHARS:
            raise ValueError("project overview budget exceeds the v2 safety limit")
        self.handler = handler
        self.max_units = max_units
        self.max_source_chars = max_source_chars
        self.max_project_overview_chars = max_project_overview_chars

    def run(
        self,
        candidates: Sequence[Any],
        units: Sequence[Any],
        *,
        project_title: str = "",
        human_project_summary: str | None = None,
        event_groups: Any = None,
    ) -> EntityDigestRunResult:
        candidates, diagnostics = normalize_candidates(candidates)
        units, unit_diagnostics = normalize_units(units)
        diagnostics.extend(unit_diagnostics)
        entity_map = {item.candidate_id: item for item in candidates if item.kind is CandidateKind.ENTITY}
        unit_map = {item.unit_id: item for item in units}
        bundles, bundle_map = self._evidence(candidates, unit_map, diagnostics)
        overview = self._overview(project_title, human_project_summary, event_groups, units, diagnostics)
        catalog = self._catalog(candidates)
        records: list[EntityDigestCallRecord] = []
        digests: list[EntityDigest] = []
        for candidate in candidates:
            candidate_records, digest = self._run_candidate(
                candidate,
                units,
                unit_map,
                entity_map,
                bundle_map.get(candidate.candidate_id),
                catalog,
                overview,
                project_title,
                diagnostics,
            )
            records.extend(candidate_records)
            diagnostics.extend(
                item
                for record in candidate_records
                for item in record.diagnostics
            )
            if digest is not None:
                digests.append(digest)
        merges = recompute_semantic_merges(
            digests,
            entity_map,
            {unit.unit_id: index for index, unit in enumerate(units)},
        )
        return EntityDigestRunResult(
            project_overview=overview,
            evidence_bundles=tuple(bundles),
            digests=tuple(digests),
            semantic_merges=tuple(merges),
            call_records=tuple(records),
            diagnostics=tuple(diagnostics),
        )

    def sample_preview(self, candidate: Any, units: Sequence[Any]) -> SamplingResult:
        candidates, candidate_diagnostics = normalize_candidates([candidate])
        if not candidates:
            raise ValueError("Cannot sample units for an invalid candidate")
        normalized_units, unit_diagnostics = normalize_units(units)
        raw = sample_entity_units(
            candidates[0].candidate_id,
            candidates[0].local_unit_ids,
            [unit.model_dump(mode="json") for unit in normalized_units],
            max_units=self.max_units,
            max_source_chars=self.max_source_chars,
        )
        result = self._sampling(raw)
        return result.model_copy(update={
            "diagnostics": tuple([
                *candidate_diagnostics,
                *unit_diagnostics,
                *result.diagnostics,
            ])
        })
    def _run_candidate(
        self,
        candidate: DigestCandidate,
        units: Sequence[DigestLocalUnit],
        unit_map: Mapping[str, DigestLocalUnit],
        entity_map: Mapping[str, DigestCandidate],
        evidence_bundle: EntityEvidenceBundle | None,
        catalog: Sequence[Mapping[str, Any]],
        overview: ProjectOverview,
        project_title: str,
        diagnostics: list[EntityDigestDiagnostic],
    ) -> tuple[list[EntityDigestCallRecord], EntityDigest | None]:
        if not self._eligible(candidate):
            return [self._skipped(candidate, diagnostics)], None
        assert evidence_bundle is not None
        segments = self._segments(candidate, units)
        if len(segments) == 1:
            outcome = self._call_segment(
                candidate, segments[0], "single", catalog, overview, project_title,
                entity_map, unit_map, evidence_bundle,
            )
            if outcome[1] is None:
                return [outcome[0]], None
            return [outcome[0]], self._finalize_digest(
                outcome[1], evidence_bundle, self._segment_membership(segments), (),
            )
        records: list[EntityDigestCallRecord] = []
        partials: list[PartialEntityDigest] = []
        for segment in segments:
            record, partial = self._call_segment(
                candidate, segment, "partial", catalog, overview, project_title,
                entity_map, unit_map, evidence_bundle,
            )
            records.append(record)
            if partial is not None:
                partials.append(PartialEntityDigest(
                    digest_segment_id=segment.metadata.digest_segment_id or "unknown-segment",
                    candidate_id=candidate.candidate_id,
                    summary=partial.summary,
                    evidence_unit_ids=partial.evidence_unit_ids,
                    batch_indexes=segment.metadata.batch_indexes,
                ))
        incomplete_partials = [
            record for record, partial in zip(records, partials, strict=False)
            if record.status != "succeeded" or partial.summary.strip() == ""
        ]
        if len(partials) != len(segments) or incomplete_partials:
            failure = diagnostic(
                "partial_digest_incomplete",
                candidate.candidate_id,
                "Final reduction was skipped because at least one evidence segment has no valid partial digest.",
            )
            diagnostics.append(failure)
            records.append(self._blocked_final(candidate, failure))
            return records, self._fallback_digest(
                candidate,
                evidence_bundle,
                self._segment_membership(segments),
                partials,
                segments[-1].metadata,
            )
        final_record, final_digest = self._final_reduction(
            candidate, catalog, overview, project_title, entity_map,
            segments, partials,
        )
        records.append(final_record)
        if final_digest is None:
            diagnostics.append(diagnostic(
                "final_digest_reduction_unavailable",
                candidate.candidate_id,
                "Partial digests were retained without a final reduction.",
            ))
            return records, self._fallback_digest(
                candidate,
                evidence_bundle,
                self._segment_membership(segments),
                partials,
                segments[-1].metadata,
            )
        return records, self._finalize_digest(
            final_digest,
            evidence_bundle,
            self._segment_membership(segments),
            tuple(partials),
        )

    def _call_segment(
        self,
        candidate: DigestCandidate,
        sampling: SamplingResult,
        phase: str,
        catalog: Sequence[Mapping[str, Any]],
        overview: ProjectOverview,
        project_title: str,
        candidates: Mapping[str, DigestCandidate],
        units: Mapping[str, DigestLocalUnit],
        evidence_bundle: EntityEvidenceBundle,
    ) -> tuple[EntityDigestCallRecord, EntityDigest | None]:
        segment_id = sampling.metadata.digest_segment_id
        payload = self._payload(candidate, catalog, overview, sampling, project_title, phase)
        messages = tuple(build_entity_digest_messages(payload))
        diagnostics = list(sampling.diagnostics)
        try:
            response, response_payload, parsed = parse_digest_response(
                self._generate(messages), max_evidence_units=self.max_units,
            )
            diagnostics.extend(parsed)
            digest = accept_digest_response(
                response, candidate, sampling, candidates, units, evidence_bundle,
                diagnostics, digest_segment_id=segment_id,
            )
            record = EntityDigestCallRecord(
                candidate_id=candidate.candidate_id,
                status="succeeded" if digest is not None else "invalid_response",
                phase=phase,
                digest_segment_id=segment_id,
                messages=messages,
                sampling=sampling.metadata,
                response_payload=response_payload,
                digest=digest,
                diagnostics=tuple(diagnostics),
            )
            return record, digest
        except (ValidationError, TypeError, ValueError) as error:
            diagnostics.append(diagnostic("invalid_digest_response", candidate.candidate_id, str(error)[:500]))
            return self._failed_record(candidate, sampling, messages, diagnostics, phase, "invalid_response"), None
        except Exception as error:
            diagnostics.append(diagnostic("entity_digest_handler_error", candidate.candidate_id, str(error)[:500]))
            return self._failed_record(candidate, sampling, messages, diagnostics, phase, "handler_error"), None
    def _final_reduction(
        self,
        candidate: DigestCandidate,
        catalog: Sequence[Mapping[str, Any]],
        overview: ProjectOverview,
        project_title: str,
        candidates: Mapping[str, DigestCandidate],
        segments: Sequence[SamplingResult],
        partials: Sequence[PartialEntityDigest],
    ) -> tuple[EntityDigestCallRecord, EntityDigest | None]:
        payload = {
            "schema_version": "context-tree-v2-entity-digest-v1",
            "phase": "final_reduction",
            "project_title": project_title or "Untitled project",
            "project_summary": overview.text,
            "candidate_catalog": list(catalog),
            "focus_candidate": {"candidate_id": candidate.candidate_id, "compact_name": candidate.compact_name},
            "partial_digests": [item.model_dump(mode="json") for item in partials],
            "digest_segment_ids": [item.metadata.digest_segment_id for item in segments],
        }
        messages = tuple(build_entity_digest_messages(payload))
        diagnostics: list[EntityDigestDiagnostic] = []
        try:
            response, response_payload, parsed = parse_digest_response(
                self._generate(messages), max_evidence_units=self.max_units,
            )
            diagnostics.extend(parsed)
            if response.candidate_id != candidate.candidate_id:
                diagnostics.append(diagnostic("response_candidate_id_mismatch", candidate.candidate_id, "Final reduction returned another candidate."))
                return self._failed_final(candidate, messages, diagnostics, response_payload)
            merge = validate_semantic_merge(response.semantic_merge, candidate, candidates, diagnostics)
            digest = EntityDigest(
                candidate_id=candidate.candidate_id,
                summary=response.summary,
                llm_digest=response.summary,
                final_digest=response.summary,
                semantic_merge=merge,
                evidence_unit_ids=tuple(dict.fromkeys(
                    unit_id
                    for partial in partials
                    for unit_id in partial.evidence_unit_ids
                )),
                sampling=segments[-1].metadata,
            )
            return EntityDigestCallRecord(
                candidate_id=candidate.candidate_id,
                status="succeeded",
                phase="final",
                digest_segment_id="final-reduction",
                messages=messages,
                response_payload=response_payload,
                digest=digest,
                diagnostics=tuple(diagnostics),
            ), digest
        except (ValidationError, TypeError, ValueError) as error:
            diagnostics.append(diagnostic("invalid_final_digest_response", candidate.candidate_id, str(error)[:500]))
            return self._failed_final(candidate, messages, diagnostics)
        except Exception as error:
            diagnostics.append(diagnostic("final_digest_handler_error", candidate.candidate_id, str(error)[:500]))
            return self._failed_final(candidate, messages, diagnostics)
    def _segments(
        self,
        candidate: DigestCandidate,
        units: Sequence[DigestLocalUnit],
    ) -> list[SamplingResult]:
        raw_segments = segment_entity_units(
            candidate.candidate_id,
            candidate.local_unit_ids,
            [unit.model_dump(mode="json") for unit in units],
            max_units=self.max_units,
            max_source_chars=self.max_source_chars,
        )
        return [self._sampling(raw) for raw in raw_segments]
    @staticmethod
    def _sampling(raw: Mapping[str, Any]) -> SamplingResult:
        return SamplingResult(
            units=tuple(SampledLocalUnit.model_validate(item) for item in raw["units"]),
            metadata=SamplingMetadata.model_validate(raw["metadata"]),
            diagnostics=tuple(
                EntityDigestDiagnostic.model_validate(item)
                for item in raw["diagnostics"]
            ),
        )
    @staticmethod
    def _segment_membership(segments: Sequence[SamplingResult]) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {}
        for segment in segments:
            segment_id = segment.metadata.digest_segment_id
            if not segment_id:
                continue
            for unit in segment.units:
                result.setdefault(unit.unit_id, []).append(segment_id)
        return {unit_id: tuple(ids) for unit_id, ids in result.items()}
    @staticmethod
    def _finalize_digest(
        digest: EntityDigest,
        bundle: EntityEvidenceBundle,
        membership: Mapping[str, tuple[str, ...]],
        partials: Sequence[PartialEntityDigest],
    ) -> EntityDigest:
        full_evidence = tuple(record.model_copy(update={
            "included_in_digest": record.unit_id in membership,
            "digest_segment_id": (membership.get(record.unit_id) or (None,))[0],
            "digest_segment_ids": membership.get(record.unit_id, ()),
        }) for record in bundle.full_evidence)
        return digest.model_copy(update={
            "summary": digest.final_digest or digest.llm_digest or digest.summary,
            "digest_status": "complete",
            "llm_digest": digest.final_digest or digest.llm_digest or digest.summary,
            "final_digest": digest.final_digest or digest.llm_digest or digest.summary,
            "mechanical_local_description": bundle.mechanical_local_description,
            "full_evidence": full_evidence,
            "partial_digests": tuple(partials),
            "digest_segment_id": "final-reduction" if partials else digest.digest_segment_id,
            "evidence_unit_ids": tuple(record.unit_id for record in full_evidence if record.included_in_digest),
        })
    @staticmethod
    def _fallback_digest(
        candidate: DigestCandidate,
        bundle: EntityEvidenceBundle,
        membership: Mapping[str, tuple[str, ...]],
        partials: Sequence[PartialEntityDigest],
        sampling: SamplingMetadata,
    ) -> EntityDigest:
        return EntityDigest(
            candidate_id=candidate.candidate_id,
            summary="",
            digest_status="incomplete",
            llm_digest="",
            final_digest="",
            mechanical_local_description=bundle.mechanical_local_description,
            full_evidence=tuple(record.model_copy(update={
                "included_in_digest": record.unit_id in membership,
                "digest_segment_id": (membership.get(record.unit_id) or (None,))[0],
                "digest_segment_ids": membership.get(record.unit_id, ()),
            }) for record in bundle.full_evidence),
            partial_digests=tuple(partials),
            evidence_unit_ids=tuple(record.unit_id for record in bundle.full_evidence if record.unit_id in membership),
            sampling=sampling,
        )
    @staticmethod
    def _eligible(candidate: DigestCandidate) -> bool:
        return candidate.kind is CandidateKind.ENTITY and candidate.grade in {CandidateGrade.A, CandidateGrade.B}

    @staticmethod
    def _evidence(
        candidates: Sequence[DigestCandidate],
        units: Mapping[str, DigestLocalUnit],
        diagnostics: list[EntityDigestDiagnostic],
    ) -> tuple[list[EntityEvidenceBundle], dict[str, EntityEvidenceBundle]]:
        bundles: list[EntityEvidenceBundle] = []
        by_candidate: dict[str, EntityEvidenceBundle] = {}
        for candidate in candidates:
            if candidate.kind is not CandidateKind.ENTITY:
                continue
            bundle, bundle_diagnostics = build_evidence_bundle(candidate, units)
            bundles.append(bundle)
            by_candidate[candidate.candidate_id] = bundle
            diagnostics.extend(bundle_diagnostics)
        return bundles, by_candidate

    def _overview(self, title: str, summary: str | None, groups: Any, units: Sequence[DigestLocalUnit], diagnostics: list[EntityDigestDiagnostic]) -> ProjectOverview:
        raw = build_program_project_overview(title, summary, group_records(groups), [{"unit_id": unit.unit_id, "summary": unit.fragment_summary} for unit in units], max_chars=self.max_project_overview_chars)
        diagnostics.extend(EntityDigestDiagnostic.model_validate(item) for item in raw["diagnostics"])
        return ProjectOverview.model_validate({key: value for key, value in raw.items() if key != "diagnostics"})

    @staticmethod
    def _catalog(candidates: Sequence[DigestCandidate]) -> list[dict[str, Any]]:
        eligible = [
            item for item in candidates
            if item.kind is CandidateKind.ENTITY
        ]
        return [{
            "candidate_id": item.candidate_id,
            "compact_name": item.compact_name[:MAX_DIGEST_CATALOG_NAME_CHARS],
            "local_description": item.local_description[:MAX_DIGEST_CATALOG_DESCRIPTION_CHARS],
            "candidate_grade": item.grade.value,
            "kind": item.kind.value,
        } for item in eligible[:MAX_DIGEST_CATALOG_ITEMS]]

    @staticmethod
    def _payload(candidate: DigestCandidate, catalog: Sequence[Mapping[str, Any]], overview: ProjectOverview, sampling: SamplingResult, project_title: str, phase: str) -> dict[str, Any]:
        return {
            "schema_version": "context-tree-v2-entity-digest-v1",
            "phase": phase,
            "project_title": project_title or "Untitled project",
            "project_summary": overview.text,
            "project_summary_source": overview.source,
            "candidate_catalog": list(catalog),
            "focus_candidate": {"candidate_id": candidate.candidate_id, "compact_name": candidate.compact_name, "local_description": candidate.local_description, "aliases": list(candidate.aliases), "candidate_grade": candidate.grade.value, "known_local_unit_ids": list(candidate.local_unit_ids)},
            "local_units": [unit.model_dump(mode="json") for unit in sampling.units],
            "sampling_metadata": sampling.metadata.model_dump(mode="json"),
        }

    def _generate(self, messages: Sequence[Mapping[str, str]]) -> Any:
        structured = getattr(self.handler, "generate_structured_with_messages", None)
        if callable(structured):
            return structured(list(messages), schema=EntityDigestResponse.model_json_schema(), schema_name=ENTITY_DIGEST_SCHEMA_NAME, temperature=0.0)
        generate = getattr(self.handler, "generate_with_messages", None)
        if callable(generate):
            return generate(list(messages), temperature=0.0)
        raise TypeError("Injected handler must provide a fake-compatible generate method.")

    @staticmethod
    def _skipped(candidate: DigestCandidate, diagnostics: list[EntityDigestDiagnostic]) -> EntityDigestCallRecord:
        item = diagnostic("c_candidate_digest_skipped" if candidate.kind is CandidateKind.ENTITY else "non_entity_candidate_skipped", candidate.candidate_id, "C candidates stay compact." if candidate.kind is CandidateKind.ENTITY else "Only entity candidates are digested.")
        diagnostics.append(item)
        return EntityDigestCallRecord(candidate_id=candidate.candidate_id, status="skipped", phase="skipped", diagnostics=(item,))

    @staticmethod
    def _blocked_final(
        candidate: DigestCandidate,
        failure: EntityDigestDiagnostic,
    ) -> EntityDigestCallRecord:
        return EntityDigestCallRecord(
            candidate_id=candidate.candidate_id,
            status="skipped",
            phase="final",
            digest_segment_id="final-reduction",
            diagnostics=(failure,),
        )

    @staticmethod
    def _failed_record(candidate: DigestCandidate, sampling: SamplingResult, messages: tuple[dict[str, str], ...], diagnostics: Sequence[EntityDigestDiagnostic], phase: str, status: str) -> EntityDigestCallRecord:
        return EntityDigestCallRecord(candidate_id=candidate.candidate_id, status=status, phase=phase, digest_segment_id=sampling.metadata.digest_segment_id, messages=messages, sampling=sampling.metadata, diagnostics=tuple(diagnostics))

    @staticmethod
    def _failed_final(candidate: DigestCandidate, messages: tuple[dict[str, str], ...], diagnostics: Sequence[EntityDigestDiagnostic], payload: Mapping[str, Any] | None = None) -> tuple[EntityDigestCallRecord, None]:
        return EntityDigestCallRecord(candidate_id=candidate.candidate_id, status="invalid_response", phase="final", digest_segment_id="final-reduction", messages=messages, response_payload=dict(payload) if payload else None, diagnostics=tuple(diagnostics)), None
