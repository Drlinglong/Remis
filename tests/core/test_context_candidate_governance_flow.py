from pathlib import Path
from types import SimpleNamespace

from scripts.core.context_local_units import DeliveryAssignment, DeliveryLink
from scripts.core.neologism_extraction import (
    AnalysisScope,
    EventChainContribution,
    SourceEvidence,
    SourceItem,
    StructuredNeologismExtraction,
    TermContribution,
)
from scripts.core.services.context_candidate_adapter import ContextCandidateAdapter
from scripts.core.services.context_candidate_governance_flow_service import (
    ContextCandidateGovernanceFlowService,
    ContextCandidateGovernanceIntegrationService,
)
from scripts.core.services.context_release_assembler import ContextReleaseAssembler
from scripts.core.services.context_synthesis_service import ContextSynthesisService
from scripts.core.services.context_source_parser import ParsedSourceFile
from scripts.schemas.context import ContextAggregate, ContextContribution, ContextSourceItem


class FakeCandidateStore:
    def __init__(self):
        self.items = []

    def load_candidates(self, project_id):
        return [item for item in self.items if item.project_id == project_id]

    def save_candidates(self, project_id, candidates):
        self.items = [item for item in candidates if item.project_id == project_id]


class FakeReviewMiner:
    def __init__(self):
        self.last_candidates = []

    def review_terms(self, candidates, **kwargs):
        del kwargs
        self.last_candidates = list(candidates)
        return {
            item["original"]: SimpleNamespace(
                suggestion=f"译-{item['original']}",
                reasoning="governed review",
                confidence=0.8,
            )
            for item in candidates
        }


class FakeStatusService:
    def begin_stage(self, *args, **kwargs):
        del args, kwargs

    def record_batch(self, *args, **kwargs):
        del args, kwargs

    def complete_stage(self, *args, **kwargs):
        del args, kwargs


class MemoryRepository:
    def __init__(self):
        self.contributions = {}

    def create_contribution(self, item):
        self.contributions[item.contribution_id] = item
        return item


def _candidate(
    name,
    aggregate_key,
    *,
    kind="named_entity",
    summary_eligible=True,
    glossary_eligible=True,
    audit_only=False,
):
    return {
        "aggregate_key": aggregate_key,
        "canonical_display_name": name,
        "normalized_match_key": name.casefold(),
        "aliases": [name, f"{name} alias"],
        "candidate_kind": kind,
        "tier": "tier_1" if summary_eligible else "tier_3",
        "mention_count": 3,
        "source_item_coverage": 2,
        "local_unit_coverage": 2,
        "event_chain_coverage": 1,
        "policy_coverage": 2,
        "coverage_metrics": {
            "mention_count": 3,
            "source_item_coverage": 2,
            "local_unit_coverage": 2,
            "event_chain_coverage": 1,
        },
        "policy_reasons": ["explicit test policy"],
        "summary_eligible": summary_eligible,
        "glossary_eligible": glossary_eligible,
        "audit_only": audit_only,
        "override_provenance": {"source": "governance-core"},
    }


class FakeGovernanceCore:
    def __init__(self):
        self.calls = []
        self.candidates = [
            _candidate("Republic", "candidate:republic"),
            _candidate(
                "Incidental", "candidate:incidental", summary_eligible=False,
                glossary_eligible=False, audit_only=True,
            ),
            _candidate(
                "Core term", "candidate:core-term", kind="glossary_term",
                summary_eligible=False,
            ),
            _candidate(
                "Named phrase", "candidate:named-phrase", kind="named_phrase",
                summary_eligible=False, glossary_eligible=False,
            ),
        ]

    def aggregate_key_for_surface(self, surface):
        normalized = " ".join(str(surface).casefold().split())
        if normalized in {"republic", "republic alias"}:
            return "candidate:republic"
        if normalized == "incidental":
            return "candidate:incidental"
        if normalized == "core term":
            return "candidate:core-term"
        if normalized == "named phrase":
            return "candidate:named-phrase"
        return f"candidate:{normalized}"

    def govern(self, extractions, **kwargs):
        assignments = list(kwargs["final_delivery_assignments"])
        assigned_non_theme_links = [
            link
            for assignment in assignments
            if assignment.assignment_state == "assigned"
            for link in assignment.links
            if link.relation != "theme_related"
        ]
        self.calls.append({"extractions": extractions, **kwargs})
        return SimpleNamespace(
            candidates=self.candidates,
            policy_by_aggregate_key={
                candidate["aggregate_key"]: candidate for candidate in self.candidates
            },
            governed_extractions=list(extractions),
            synthesis_eligible_aggregate_keys={"candidate:republic"},
            glossary_eligible_match_keys={"republic", "republic alias", "core term"},
            report={
                "event_chain_coverage": len(assigned_non_theme_links),
                "assigned_delivery_link_count": len(assigned_non_theme_links),
            },
            aggregate_key_for_surface=self.aggregate_key_for_surface,
        )


def _source_items():
    return [
        SourceItem(
            source_item_id="source-1",
            relative_path="localisation/main.yml",
            item_key="first:0",
            source_order=0,
            source_text="Republic",
        ),
        SourceItem(
            source_item_id="source-2",
            relative_path="localisation/main.yml",
            item_key="second:0",
            source_order=1,
            source_text="Republic alias",
        ),
    ]


def _extraction(items):
    def evidence(item):
        return [SourceEvidence(source_item_id=item.source_item_id, snippet=item.source_text)]

    return StructuredNeologismExtraction(
        terms=[
            TermContribution(original="Republic", evidence=evidence(items[0])),
            TermContribution(original="Republic alias", evidence=evidence(items[1])),
            TermContribution(original="Incidental", evidence=evidence(items[0])),
            TermContribution(original="Core term", evidence=evidence(items[0])),
            TermContribution(original="Named phrase", evidence=evidence(items[1])),
        ],
        events=[EventChainContribution(
            chain_id="republic-chain",
            event="Republic event",
            sequence=0,
            evidence=evidence(items[0]),
        )],
    )


def _parsed_files(items):
    return [ParsedSourceFile(
        path=Path("main.yml"),
        relative_path="localisation/main.yml",
        content=b"",
        items=tuple(items),
        parse_summary={},
    )]


def _governance(extractions, reconciled=None, core=None):
    core = core or FakeGovernanceCore()
    return ContextCandidateGovernanceIntegrationService(core).govern(
        project_id="project-1",
        extractions=extractions,
        analysis_scope=AnalysisScope.NARRATIVE_CONTEXT,
        source_items=_source_items(),
        reconciled=reconciled,
    )


def test_candidate_adapter_reviews_and_saves_only_glossary_eligible_terms():
    items = _source_items()
    store = FakeCandidateStore()
    miner = FakeReviewMiner()
    governance = _governance([_extraction(items)])

    result = ContextCandidateAdapter(store).process_terms(
        "project-1",
        _parsed_files(items),
        [_extraction(items)],
        miner,
        {},
        "en",
        "zh-CN",
        "Vic3",
        "en",
        governance=governance,
    )

    assert result["new_terms"] == 3
    assert [item["original"] for item in miner.last_candidates] == [
        "Republic", "Republic alias", "Core term",
    ]
    assert {item.original for item in store.items} == {
        "Republic", "Republic alias", "Core term",
    }
    assert "Incidental" not in {item.original for item in store.items}
    assert "Named phrase" not in {item.original for item in store.items}


def test_all_governed_aggregates_persist_aliases_merge_and_audit_is_excluded_from_project_summary():
    items = _source_items()
    sources = {
        item.source_item_id: ContextSourceItem(
            source_item_id=item.source_item_id,
            project_id="project-1",
            source_type="localization",
            source_ref=f"{item.relative_path}::{item.source_order}:{item.item_key}",
            content=item.source_text,
            content_hash=f"hash-{item.source_item_id}",
        )
        for item in items
    }
    extraction = _extraction(items)
    governance = _governance([extraction])
    assembler = ContextReleaseAssembler(MemoryRepository())
    contributions = assembler.persist_contributions(
        [extraction], sources, governance.aggregate_key_for_surface,
    )
    aggregates = assembler.build_aggregates("project-1", contributions, governance)
    by_key = {aggregate.aggregate_key: aggregate for aggregate in aggregates}

    assert {
        "candidate:republic", "candidate:incidental", "candidate:core-term",
        "candidate:named-phrase", "event:republic-chain",
    } <= set(by_key)
    assert len(by_key["candidate:republic"].contribution_ids) == 2
    assert "candidate:incidental" in {
        contribution.subject_key for contribution in contributions.values()
    }
    project_ids = set(by_key["project:summary"].contribution_ids)
    incidental_ids = {
        contribution.contribution_id
        for contribution in contributions.values()
        if contribution.subject_key == "candidate:incidental"
    }
    assert not project_ids & incidental_ids
    required = {
        "canonical_display_name", "normalized_match_key", "aliases", "candidate_kind",
        "tier", "mention_count", "source_item_coverage", "local_unit_coverage",
        "event_chain_coverage", "policy_coverage", "coverage_metrics", "policy_reasons",
        "summary_eligible",
        "glossary_eligible", "audit_only", "override_provenance",
    }
    assert required <= set(by_key["candidate:incidental"].payload)
    assert by_key["candidate:incidental"].payload["audit_only"] is True
    assert by_key["candidate:named-phrase"].payload["summary_eligible"] is False


def test_only_explicit_synthesis_eligible_candidates_reach_the_context_prompt():
    items = _source_items()
    extraction = _extraction(items)
    governance = _governance([extraction])
    sources = {
        item.source_item_id: ContextSourceItem(
            source_item_id=item.source_item_id,
            project_id="project-1",
            source_type="localization",
            source_ref=item.item_key or item.relative_path,
            content=item.source_text,
            content_hash=f"hash-{item.source_item_id}",
        )
        for item in items
    }
    assembler = ContextReleaseAssembler(MemoryRepository())
    contributions = assembler.persist_contributions(
        [extraction], sources, governance.aggregate_key_for_surface,
    )
    aggregates = assembler.build_aggregates("project-1", contributions, governance)
    eligible = ContextCandidateGovernanceFlowService.synthesis_eligible_aggregates(
        aggregates, governance,
    )
    prompt = ContextSynthesisService._request_payload(
        eligible, contributions, sources,
    ).payload_json

    assert [aggregate.aggregate_key for aggregate in eligible] == [
        "candidate:republic", "event:republic-chain", "project:summary",
    ]
    eligibility = {
        aggregate.aggregate_key: aggregate.payload.get("synthesis_required")
        for aggregate in aggregates
    }
    assert eligibility == {
        "candidate:core-term": False,
        "candidate:incidental": False,
        "candidate:named-phrase": False,
        "candidate:republic": True,
        "event:republic-chain": True,
        "project:summary": True,
    }
    assert "Incidental" not in prompt
    assert "Republic" in prompt
    assert "candidate:incidental" not in {
        aggregate.aggregate_key for aggregate in eligible
    }


def test_governance_receives_final_assigned_non_theme_delivery_links():
    assignments = [
        DeliveryAssignment(
            local_unit_id="unit_0",
            assignment_state="assigned",
            source_item_ids=["source-1"],
            links=[DeliveryLink(
                event_chain_id="republic-chain",
                relation="primary_member",
                confidence=0.9,
            )],
        ),
        DeliveryAssignment(
            local_unit_id="unit_1",
            assignment_state="assigned",
            source_item_ids=["source-2"],
            links=[DeliveryLink(
                event_chain_id="theme-chain",
                relation="theme_related",
                confidence=0.4,
            )],
        ),
        DeliveryAssignment(
            local_unit_id="unit_2",
            assignment_state="unassigned",
            source_item_ids=["source-3"],
            links=[DeliveryLink(
                event_chain_id="unassigned-chain",
                relation="primary_member",
                confidence=0.2,
            )],
        ),
    ]
    core = FakeGovernanceCore()
    result = _governance(
        [StructuredNeologismExtraction()],
        SimpleNamespace(delivery_assignments=assignments),
        core,
    )

    call = core.calls[0]
    assert call["final_delivery_assignments"] == assignments
    assert call["final_assignments"] == assignments
    assert call["final_delivery_links"] == assignments
    assert call["final_local_unit_delivery_links"] == assignments
    assert result.report["event_chain_coverage"] == 1
    assert result.report["assigned_delivery_link_count"] == 1


def test_legacy_extractions_remain_accepted_when_governance_core_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        ContextCandidateGovernanceIntegrationService,
        "_load_default_service",
        staticmethod(lambda: None),
    )
    extraction = StructuredNeologismExtraction()
    result = ContextCandidateGovernanceIntegrationService(None).govern(
        project_id="project-1",
        extractions=[extraction],
        analysis_scope=AnalysisScope.TERMS_ONLY,
    )

    assert result.available is False
    assert result.governed_extractions == (extraction,)
    assert result.synthesis_eligible_aggregate_keys == frozenset()


def test_legacy_checkpoint_extraction_payload_remains_accepted(monkeypatch):
    monkeypatch.setattr(
        ContextCandidateGovernanceIntegrationService,
        "_load_default_service",
        staticmethod(lambda: None),
    )
    legacy_payload = {
        "terms": [{
            "original": "Republic",
            "category": "concept",
            "confidence": 0.8,
            "evidence": [{"source_item_id": "source-1"}],
        }],
    }
    extraction = StructuredNeologismExtraction.model_validate(legacy_payload)
    result = ContextCandidateGovernanceIntegrationService(None).govern(
        project_id="project-1",
        extractions=[extraction],
        analysis_scope=AnalysisScope.TERMS_ONLY,
    )

    assert result.governed_extractions[0].terms[0].original == "Republic"
