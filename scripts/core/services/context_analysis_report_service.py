"""Build an auditable smoke-report payload from one context-analysis run."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Sequence

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import SourceItem, StructuredNeologismExtraction
from scripts.core.provider_structured_output import structured_output_mode
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_event_reconciliation_service import EventReconciliationResult


class ContextAnalysisReportService:
    """Expose deterministic coverage facts without pretending to judge semantics."""

    @classmethod
    def build(
        cls,
        source_items: Sequence[SourceItem],
        local_units: Sequence[LocalTextUnit],
        chunks: Sequence[ContextUnitChunk],
        local_extractions: Sequence[StructuredNeologismExtraction],
        reconciled: EventReconciliationResult,
        *,
        provider: str,
        model: str | None,
        effective_concurrency: int,
        prompt_version: str,
        parsed_files: Sequence[Any] = (),
        model_execution: dict[str, Any] | None = None,
        governance: Any | None = None,
    ) -> dict[str, Any]:
        unit_chunk = cls._unit_chunk_index(chunks)
        final_assignments = reconciled.delivery_assignments
        input_unit_ids = [unit.unit_id for unit in local_units]
        assignment_ids = [item.local_unit_id for item in final_assignments]
        assignment_counts = Counter(assignment_ids)
        unassigned = [
            item for item in final_assignments if item.assignment_state == "unassigned"
        ]
        multi_linked = [
            item for item in final_assignments
            if len({link.event_chain_id for link in item.links}) > 1
        ]
        execution = model_execution or cls._empty_model_execution()
        return {
            "input_and_chunking": cls._input_report(
                source_items, local_units, chunks, provider, model,
                effective_concurrency, prompt_version, execution,
            ),
            "source_integrity": cls._source_integrity_report(parsed_files, source_items),
            "unit_assignment_integrity": {
                "input_units": len(input_unit_ids),
                "assignment_records": len(assignment_ids),
                "missing": sorted(set(input_unit_ids) - set(assignment_ids)),
                "duplicate": sorted(
                    unit_id for unit_id, count in assignment_counts.items() if count > 1
                ),
                "unexpected": sorted(set(assignment_ids) - set(input_unit_ids)),
                "unassigned": len(unassigned),
                "multi_linked": len(multi_linked),
                "repair_count": sum(
                    int(item.diagnostics.get("repair_count") or 0)
                    for item in local_extractions
                ) + int(reconciled.diagnostics.get("repair_count") or 0),
                "repair_reasons": cls._repair_reasons(
                    local_extractions, reconciled,
                ),
                "one_to_one_after_repair": (
                    len(assignment_ids) == len(input_unit_ids)
                    and set(assignment_ids) == set(input_unit_ids)
                    and all(count == 1 for count in assignment_counts.values())
                ),
            },
            "final_chain_resolution": cls._chain_report(
                local_extractions, reconciled,
            ),
            "chunk_boundary_impact": cls._boundary_report(
                chunks, local_extractions, reconciled,
            ),
            "coverage_and_contamination": cls._coverage_report(
                source_items, final_assignments,
            ),
            "unassigned_units": cls._unassigned_report(
                local_units, unassigned, unit_chunk,
            ),
            "candidate_governance": cls._candidate_governance_report(governance),
            "model_execution": execution,
        }

    @classmethod
    def governance_only(cls, governance: Any | None) -> dict[str, Any]:
        """Return the same governance report shape for terms-only workflows."""

        return {"candidate_governance": cls._candidate_governance_report(governance)}

    @staticmethod
    def _candidate_governance_report(governance: Any | None) -> dict[str, Any]:
        if governance is None:
            return {
                "available": False,
                "counts": {},
                "report": {},
            }
        report_payload = getattr(governance, "report_payload", None)
        if callable(report_payload):
            return dict(report_payload())
        return {
            "available": bool(getattr(governance, "available", False)),
            "counts": dict(getattr(governance, "counts", {}) or {}),
            "report": dict(getattr(governance, "report", {}) or {}),
        }

    @staticmethod
    def _input_report(
        source_items: Sequence[SourceItem],
        local_units: Sequence[LocalTextUnit],
        chunks: Sequence[ContextUnitChunk],
        provider: str,
        model: str | None,
        concurrency: int,
        prompt_version: str,
        model_execution: dict[str, Any],
    ) -> dict[str, Any]:
        core_occurrences = Counter(
            unit.unit_id for chunk in chunks for unit in chunk.core_units
        )
        return {
            "source_items": len(source_items),
            "local_units": len(local_units),
            "chunks": len(chunks),
            "core_units_per_chunk": [len(chunk.core_units) for chunk in chunks],
            "edge_units_per_chunk": [len(chunk.edge_units) for chunk in chunks],
            "unit_split_across_chunks": (
                set(core_occurrences) != {unit.unit_id for unit in local_units}
                or any(count != 1 for count in core_occurrences.values())
            ),
            "project_unique_unit_ids": len({unit.unit_id for unit in local_units}) == len(local_units),
            "provider": provider,
            "model": model or f"{provider}-default",
            "structured_output_mode": structured_output_mode(provider),
            "reasoning_profile": model_execution.get("reasoning_profile"),
            "prompt_version": prompt_version,
            "effective_concurrency": concurrency,
            "token_usage": model_execution.get("token_usage"),
            "cost": model_execution.get("cost"),
            "usage_note": model_execution.get("usage_note"),
        }

    @staticmethod
    def _source_integrity_report(
        parsed_files: Sequence[Any], source_items: Sequence[SourceItem],
    ) -> dict[str, Any]:
        files = []
        for source_file in parsed_files:
            summary = dict(getattr(source_file, "parse_summary", {}) or {})
            files.append({
                "relative_path": str(getattr(source_file, "relative_path", "")),
                **summary,
            })
        totals = {
            key: sum(int(item.get(key) or 0) for item in files)
            for key in (
                "raw", "syntax_parsed", "policy_excluded", "eligible",
                "parse_errors", "source_items",
            )
        }
        totals["workflow_source_items"] = len(source_items)
        totals["gate_passed"] = bool(
            totals["parse_errors"] == 0
            and totals["eligible"] == totals["source_items"] == len(source_items)
        )
        return {"totals": totals, "files": files}

    @staticmethod
    def _repair_reasons(
        local_extractions: Sequence[StructuredNeologismExtraction],
        reconciled: EventReconciliationResult,
    ) -> list[dict[str, Any]]:
        reasons = [
            {
                "stage": "extraction",
                "batch_index": index,
                "reason": extraction.diagnostics.get("repair_reason"),
                "detail": extraction.diagnostics.get("first_validation_error"),
            }
            for index, extraction in enumerate(local_extractions)
            if int(extraction.diagnostics.get("repair_count") or 0)
        ]
        reasons.extend(reconciled.diagnostics.get("repair_reasons") or [])
        return reasons

    @staticmethod
    def _empty_model_execution() -> dict[str, Any]:
        return {
            "call_count": 0,
            "reasoning_profile": None,
            "token_usage": None,
            "cost": None,
            "usage_note": "No provider usage records were captured for this run.",
            "by_phase": {},
        }

    @classmethod
    def _chain_report(
        cls,
        local_extractions: Sequence[StructuredNeologismExtraction],
        reconciled: EventReconciliationResult,
    ) -> list[dict[str, Any]]:
        resolutions = reconciled.diagnostics.get("proposal_resolutions") or []
        resolution_by_final: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for resolution in resolutions:
            for chain_id in resolution.get("final_chain_ids") or []:
                resolution_by_final[chain_id].append(resolution)
        links_by_chain: dict[str, Counter[str]] = defaultdict(Counter)
        for assignment in reconciled.delivery_assignments:
            for link in assignment.links:
                links_by_chain[link.event_chain_id][link.relation] += 1
        report = []
        for event in reconciled.events:
            resolutions_for_chain = resolution_by_final.get(event.chain_id, [])
            proposal_ids = [item["proposal_id"] for item in resolutions_for_chain]
            report.append({
                "chain_id": event.chain_id,
                "chain_level": event.chain_level,
                "from_chunks": sorted({
                    int(proposal_id.split("_", 1)[0][1:]) + 1
                    for proposal_id in proposal_ids
                }),
                "local_proposals": proposal_ids,
                "split": any(
                    item.get("resolution") in {"split_required", "split_across"}
                    for item in resolutions_for_chain
                ),
                "primary_members": links_by_chain[event.chain_id]["primary_member"],
                "supporting_context": links_by_chain[event.chain_id]["supporting_context"],
                "theme_related": links_by_chain[event.chain_id]["theme_related"],
                "evidence": len(event.evidence),
                "parent_story": event.parent_story_id,
            })
        return report

    @classmethod
    def _boundary_report(
        cls,
        chunks: Sequence[ContextUnitChunk],
        local_extractions: Sequence[StructuredNeologismExtraction],
        reconciled: EventReconciliationResult,
    ) -> dict[str, Any]:
        proposals = cls._local_proposals(local_extractions, reconciled)
        final_chains = cls._chain_report(local_extractions, reconciled)
        final_links = cls._membership_set(reconciled.delivery_assignments)
        mapped_local_links = cls._mapped_local_memberships(local_extractions, reconciled)
        boundary_units = {
            unit.unit_id
            for chunk in chunks
            for unit in (chunk.core_units[:1] + chunk.core_units[-1:])
        }
        unassigned = {
            item.local_unit_id for item in reconciled.delivery_assignments
            if item.assignment_state == "unassigned"
        }
        return {
            "touching_left": [
                item["proposal_id"] for item in proposals
                if item["boundary_status"] in {"continues_before", "continues_both"}
            ],
            "touching_right": [
                item["proposal_id"] for item in proposals
                if item["boundary_status"] in {"continues_after", "continues_both"}
            ],
            "cross_chunk_merged_chains": [
                item["chain_id"] for item in final_chains if len(item["from_chunks"]) > 1
            ],
            "boundary_unassigned_units": sorted(boundary_units & unassigned),
            "membership_before": len(mapped_local_links),
            "membership_after": len(final_links),
            "membership_added": len(final_links - mapped_local_links),
            "membership_removed": len(mapped_local_links - final_links),
        }

    @staticmethod
    def _coverage_report(
        source_items: Sequence[SourceItem], assignments: Sequence[Any],
    ) -> dict[str, Any]:
        total = len(source_items)
        primary = {
            source_id for item in assignments for source_id in item.source_item_ids
            if any(link.relation == "primary_member" for link in item.links)
        }
        delivered = {
            source_id for item in assignments for source_id in item.source_item_ids
            if any(
                link.relation in {"primary_member", "supporting_context"}
                for link in item.links
            )
        }
        unassigned = {
            source_id for item in assignments for source_id in item.source_item_ids
            if item.assignment_state == "unassigned"
        }
        multi = sum(
            1 for item in assignments
            if len({link.event_chain_id for link in item.links}) > 1
        )
        return {
            "primary_membership_coverage": len(primary) / total if total else 0.0,
            "delivery_coverage": len(delivered) / total if total else 0.0,
            "unassigned_rate": len(unassigned) / total if total else 0.0,
            "multi_chain_unit_rate": multi / len(assignments) if assignments else 0.0,
            "incorrect_sibling_injection_count": None,
            "incorrect_sibling_injection_note": "Requires semantic human audit.",
            "theme_related_injection_count": 0,
            "parent_story_automatic_inheritance_count": 0,
        }

    @staticmethod
    def _unassigned_report(
        local_units: Sequence[LocalTextUnit],
        unassigned: Sequence[Any],
        unit_chunk: dict[str, int],
    ) -> list[dict[str, Any]]:
        units = {unit.unit_id: unit for unit in local_units}
        return [
            {
                "unit_id": item.local_unit_id,
                "localization_keys": [
                    source.item_key for source in units[item.local_unit_id].items
                ],
                "chunk": unit_chunk.get(item.local_unit_id),
                "model_state": item.assignment_state,
                "expected_chain": None,
                "classification": "pending_human_audit",
            }
            for item in unassigned
        ]

    @staticmethod
    def _unit_chunk_index(chunks: Sequence[ContextUnitChunk]) -> dict[str, int]:
        return {
            unit.unit_id: index
            for index, chunk in enumerate(chunks, start=1)
            for unit in chunk.core_units
        }

    @staticmethod
    def _local_proposals(
        extractions: Sequence[StructuredNeologismExtraction],
        reconciled: EventReconciliationResult,
    ) -> list[dict[str, Any]]:
        cards = reconciled.diagnostics.get("local_chain_cards") or []
        if cards:
            return [
                {
                    "proposal_id": card["proposal_id"],
                    "boundary_status": ContextAnalysisReportService._card_boundary_status(
                        card.get("steps") or []
                    ),
                }
                for card in cards
            ]
        return [
            {
                "proposal_id": f"b{batch_index}_e{event_index}",
                "boundary_status": event.boundary_status,
            }
            for batch_index, extraction in enumerate(extractions)
            for event_index, event in enumerate(extraction.events)
        ]

    @staticmethod
    def _card_boundary_status(steps: Sequence[dict[str, Any]]) -> str:
        statuses = {str(step.get("boundary_status") or "uncertain") for step in steps}
        before = bool(statuses & {"continues_before", "continues_both"})
        after = bool(statuses & {"continues_after", "continues_both"})
        if before and after:
            return "continues_both"
        if before:
            return "continues_before"
        if after:
            return "continues_after"
        if statuses == {"complete_in_chunk"}:
            return "complete_in_chunk"
        return "uncertain"

    @staticmethod
    def _membership_set(assignments: Sequence[Any]) -> set[tuple[str, str, str]]:
        return {
            (assignment.local_unit_id, link.event_chain_id, link.relation)
            for assignment in assignments for link in assignment.links
        }

    @classmethod
    def _mapped_local_memberships(
        cls,
        extractions: Sequence[StructuredNeologismExtraction],
        reconciled: EventReconciliationResult,
    ) -> set[tuple[str, str, str]]:
        resolution_map: dict[str, list[str]] = {}
        for resolution in reconciled.diagnostics.get("proposal_resolutions") or []:
            resolution_map[resolution["proposal_id"]] = resolution.get("final_chain_ids") or []
        mapped: set[tuple[str, str, str]] = set()
        final_chains_by_unit = {
            assignment.local_unit_id: {
                link.event_chain_id for link in assignment.links
            }
            for assignment in reconciled.delivery_assignments
        }
        cards = reconciled.diagnostics.get("local_chain_cards") or []
        card_by_local_chain = {
            (int(card.get("batch_index") or 0), str(card["local_chain_id"]).casefold()):
                card["proposal_id"]
            for card in cards
        }
        for batch_index, extraction in enumerate(extractions):
            proposals = {
                event.chain_id.casefold(): resolution_map.get(
                    card_by_local_chain.get(
                        (batch_index, event.chain_id.casefold()),
                        f"b{batch_index}_e{event_index}",
                    ),
                    [],
                )
                for event_index, event in enumerate(extraction.events)
            }
            for assignment in extraction.delivery_assignments:
                for link in assignment.links:
                    final_candidates = proposals.get(link.event_chain_id.casefold(), [])
                    if len(final_candidates) > 1:
                        final_candidates = [
                            chain_id for chain_id in final_candidates
                            if chain_id in final_chains_by_unit.get(
                                assignment.local_unit_id, set()
                            )
                        ]
                    for final_chain in final_candidates:
                        mapped.add((assignment.local_unit_id, final_chain, link.relation))
        return mapped
