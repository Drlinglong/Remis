import json
from pathlib import Path
from types import SimpleNamespace

from scripts.core.neologism_extraction import (
    AnalysisScope,
    EntityContribution,
    EventChainContribution,
    FactContribution,
    RelationshipContribution,
    SourceEvidence,
    SourceItem,
    StructuredNeologismExtraction,
    TermContribution,
)
from scripts.core.file_parser import extract_translatable_content
from scripts.core.loc_parser import parse_loc_file
from scripts.core.services.context_source_parser import ContextSourceParser
from scripts.core.services.context_synthesis_service import ContextSynthesisService
from scripts.core.services.context_workflow_service import ContextWorkflowService
from scripts.core.services.initial_translation_task_service import _build_source_entries
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextRelease,
    ContextSourceItem,
)


class FakeCandidateStore:
    def __init__(self):
        self.items = []

    def load_candidates(self, project_id):
        return [item for item in self.items if item.project_id == project_id]

    def save_candidates(self, project_id, candidates):
        self.items = [item for item in candidates if item.project_id == project_id]


class FakeTaskBackend:
    def __init__(self):
        self.updates = []

    def update_task(self, task_id, **payload):
        self.updates.append((task_id, payload))


class FakeRepository:
    def __init__(self):
        self.sources = {}
        self.contributions = {}
        self.aggregates = {}
        self.releases = {}

    def get_source_item(self, source_item_id):
        return self.sources.get(source_item_id)

    def create_source_item(self, item):
        self.sources[item.source_item_id] = item
        return item

    def create_contribution(self, item):
        self.contributions[item.contribution_id] = item
        return item

    def save_aggregate(self, item):
        self.aggregates[item.aggregate_id] = item
        return item

    def list_releases(self, project_id):
        return list(reversed([item for item in self.releases.values() if item.project_id == project_id]))


class FakeContextService:
    def __init__(self, repository):
        self.repository = repository
        self.drafts = {}
        self.snapshots = {}
        self.counter = 0

    def start_draft(self, project_id, base_release_id=None):
        self.counter += 1
        draft = SimpleNamespace(draft_id=f"draft-{self.counter}", project_id=project_id, base_release_id=base_release_id)
        self.drafts[draft.draft_id] = draft
        return draft

    def publish_draft(self, draft_id, metadata, aggregate_ids, syntheses):
        draft = self.drafts[draft_id]
        release_id = f"release-{len(self.repository.releases) + 1}"
        release = ContextRelease(
            release_id=release_id,
            project_id=draft.project_id,
            metadata=metadata,
        )
        self.repository.releases[release_id] = release
        self.snapshots[release_id] = {
            "aggregate_ids": list(aggregate_ids),
            "syntheses": list(syntheses),
            "contribution_ids": {
                aggregate_id: list(self.repository.aggregates[aggregate_id].contribution_ids)
                for aggregate_id in aggregate_ids
            },
        }
        return release


class FakeMiner:
    def __init__(self, handler):
        self.calls = []

    def extract_structured(self, source_items, *, scope, game_name):
        self.calls.append((list(source_items), scope, game_name))
        terms = []
        entities = []
        facts = []
        events = []
        relationships = []
        for item in source_items:
            evidence = SourceEvidence(source_item_id=item.source_item_id, snippet=item.source_text)
            terms.append(TermContribution(original="Republic", category="faction", evidence=[evidence]))
            entities.append(EntityContribution(
                name="Republic", entity_type="organization/faction", description="A polity.", evidence=[evidence]
            ))
            facts.append(FactContribution(
                subject="Republic", predicate="appoints", object="consul", evidence=[evidence]
            ))
            events.append(EventChainContribution(
                chain_id="republic-chain", event="appoints consul", sequence=item.source_order or 0,
                evidence=[evidence]
            ))
            relationships.append(RelationshipContribution(
                subject="Republic", relation="protects", object="gate", evidence=[evidence]
            ))
        return StructuredNeologismExtraction(
            terms=terms, entities=entities, facts=facts, events=events, relationships=relationships
        )

    def review_terms(self, candidates, **kwargs):
        return {
            item["original"]: SimpleNamespace(
                suggestion="共和国", reasoning="semantic translation", confidence=0.9
            )
            for item in candidates
        }


class FakeHandler:
    def __init__(self):
        self.calls = []

    def generate_with_messages(self, messages, temperature=0.0):
        self.calls.append(messages)
        request = json.loads(messages[-1]["content"])
        return json.dumps({
            "syntheses": [
                {
                    "aggregate_id": aggregate["aggregate_id"],
                    "context_key": aggregate["context_key"],
                    "summary": f"Grounded summary for {aggregate['context_key']}.",
                    "evidence_source_item_ids": [
                        contribution["source_items"][0]["source_item_id"]
                        for contribution in aggregate["contributions"]
                    ],
                }
                for aggregate in request["aggregates"]
            ]
        })


def _service(repo, candidate_store=None, task_backend=None, handler=None):
    fake_handler = handler or FakeHandler()
    return ContextWorkflowService(
        repo,
        handler_factory=lambda *args, **kwargs: fake_handler,
        candidate_store=candidate_store or FakeCandidateStore(),
        task_backend=task_backend or FakeTaskBackend(),
        miner_factory=FakeMiner,
        synthesizer_factory=ContextSynthesisService,
        context_service=FakeContextService(repo),
    )


def test_reservation_is_owned_and_released_by_context_workflow_status():
    service = _service(FakeRepository())

    assert service.reserve("project-1", "task-1", AnalysisScope.TERMS_ONLY) is True
    assert service.reserve("project-1", "task-2", AnalysisScope.NARRATIVE_CONTEXT) is False

    service._complete(
        "project-1",
        "task-1",
        {"analysis_scope": "terms_only", "new_terms": 0, "duplicate_terms": 0},
        0,
    )

    assert service.reserve("project-1", "task-2", AnalysisScope.NARRATIVE_CONTEXT) is True


def test_failed_task_creation_can_release_only_its_queued_reservation():
    service = _service(FakeRepository())
    assert service.reserve("project-1", "task-1", AnalysisScope.TERMS_ONLY) is True

    service.release_reservation("project-1", "another-task")
    assert service.reserve("project-1", "task-2", AnalysisScope.TERMS_ONLY) is False

    service.release_reservation("project-1", "task-1")
    assert service.reserve("project-1", "task-2", AnalysisScope.TERMS_ONLY) is True


def test_context_extraction_chunks_bound_structured_model_output():
    items = [
        SourceItem(
            source_item_id=f"item-{index}",
            relative_path="localisation/english/main.yml",
            item_key=f"key_{index}:0",
            source_order=index,
            source_text=f"Source text {index}",
        )
        for index in range(ContextWorkflowService.CHUNK_SIZE + 1)
    ]

    chunks = list(ContextWorkflowService._chunks(items))

    assert [len(chunk) for chunk in chunks] == [ContextWorkflowService.CHUNK_SIZE, 1]
    assert ContextWorkflowService.CHUNK_SIZE == 16


def test_source_parser_preserves_utf8_key_order_and_normalized_path(tmp_path):
    root = tmp_path / "mod"
    root.mkdir()
    path = root / "localisation" / "main.yml"
    path.parent.mkdir()
    path.write_text(
        'l_english:\n first_key:0 "第一句"\n second_key:0 "Second sentence"\n',
        encoding="utf-8",
    )

    parsed = ContextSourceParser().parse_files([str(path)], str(root))[0]

    assert parsed.relative_path == "localisation/main.yml"
    assert [(item.item_key, item.source_order, item.source_text) for item in parsed.items] == [
        ("first_key:0", 0, "第一句"),
        ("second_key:0", 1, "Second sentence"),
    ]


def test_context_items_share_translation_source_entry_key_contract(tmp_path):
    root = tmp_path / "mod"
    root.mkdir()
    path = root / "main.yml"
    path.write_text(
        'l_english:\n first_key:0 "第一句"\n second_key:0 "Second sentence"\n',
        encoding="utf-8",
    )

    parsed = ContextSourceParser().parse_files([str(path)], str(root))[0]
    _, texts, key_map = extract_translatable_content(str(path))
    translation_entries = _build_source_entries(texts, key_map)
    direct_entries = parse_loc_file(path)

    assert [(item.item_key, item.source_text) for item in parsed.items] == [
        (entry["key"], entry["source"]) for entry in translation_entries
    ] == direct_entries


def test_terms_only_uses_one_extraction_call_and_creates_no_release(tmp_path):
    root = tmp_path / "mod"
    root.mkdir()
    source = root / "main.yml"
    source.write_text('l_english:\n key:0 "The Republic appoints a consul."\n', encoding="utf-8")
    repo = FakeRepository()
    candidate_store = FakeCandidateStore()
    task_backend = FakeTaskBackend()
    miner = FakeMiner(None)
    service = ContextWorkflowService(
        repo,
        handler_factory=lambda *args, **kwargs: FakeHandler(),
        candidate_store=candidate_store,
        task_backend=task_backend,
        miner_factory=lambda handler: miner,
        context_service=FakeContextService(repo),
    )

    result = service.run(
        "project-1", [str(source)], str(root), "local", task_id="task-1", analysis_scope="terms_only"
    )

    assert result["context_release_id"] is None
    assert len(miner.calls) == 1
    assert len(candidate_store.items) == 1
    assert any(update[1].get("status") == "completed" for update in task_backend.updates)


def test_narrative_release_has_metadata_traceability_summary_and_parent_diff(tmp_path):
    root = tmp_path / "mod"
    root.mkdir()
    source = root / "main.yml"
    source.write_text(
        'l_english:\n first_key:0 "The Republic appoints a consul."\n second_key:0 "The Republic protects a gate."\n',
        encoding="utf-8",
    )
    repo = FakeRepository()
    service = _service(repo)

    first = service.run(
        "project-1", [str(source)], str(root), "local", task_id="task-1",
        analysis_scope=AnalysisScope.NARRATIVE_CONTEXT, model_name="fake-model",
    )
    assert first["context_release_id"] == "release-1"
    release = repo.releases["release-1"]
    assert release.metadata.provider_id == "local"
    assert release.metadata.model_id == "fake-model"
    assert release.metadata.schema_version == "context-v1"
    assert release.metadata.prompt_version == "context-synthesis-v1"
    assert release.metadata.parent_release_id is None
    assert any(
        item.context_key == "project:summary"
        for item in service.context_service.snapshots["release-1"]["syntheses"]
    )
    first_sources = set(repo.sources)

    source.write_text('l_english:\n first_key:0 "The Republic appoints a consul."\n', encoding="utf-8")
    second = service.run(
        "project-1", [str(source)], str(root), "local", task_id="task-2",
        analysis_scope=AnalysisScope.NARRATIVE_CONTEXT, model_name="fake-model",
    )
    second_release = repo.releases[second["context_release_id"]]
    assert second_release.metadata.parent_release_id == "release-1"
    assert second_release.metadata.source_snapshot_hash != release.metadata.source_snapshot_hash
    assert any(item["kind"] == "deleted" for item in second["affected_source_items"])
    second_contributions = set().union(*[
        set(ids) for ids in service.context_service.snapshots[second["context_release_id"]]["contribution_ids"].values()
    ])
    assert all(repo.contributions[item].source_item_id in first_sources for item in second_contributions)


def test_synthesis_repairs_at_most_once():
    source = ContextSourceItem(
        source_item_id="source-1", project_id="project-1", source_type="localization",
        source_ref="main.yml::0:key", content="The Republic appoints a consul.", content_hash="hash-1",
    )
    contribution = ContextContribution(
        contribution_id="contribution-1", source_item_id="source-1", contribution_type="fact",
        subject_key="entity:republic", payload={"evidence": [{"source_item_id": "source-1"}]},
        provenance="text_inferred",
    )
    aggregate = ContextAggregate(
        aggregate_id="aggregate-1", project_id="project-1", aggregate_type="entity",
        aggregate_key="entity:republic", contribution_ids=[contribution.contribution_id],
    )

    class RepairHandler(FakeHandler):
        def generate_with_messages(self, messages, temperature=0.0):
            self.calls.append(messages)
            if len(self.calls) == 1:
                return "not-json"
            return json.dumps({
                "syntheses": [{
                    "aggregate_id": "aggregate-1", "context_key": "entity:republic",
                    "summary": "The Republic appoints a consul.",
                    "evidence_source_item_ids": ["source-1"],
                }]
            })

    handler = RepairHandler()
    result = ContextSynthesisService(handler).synthesize(
        [aggregate], {contribution.contribution_id: contribution}, {source.source_item_id: source}
    )

    assert len(handler.calls) == 2
    assert result[0].content["evidence_source_item_ids"] == ["source-1"]
