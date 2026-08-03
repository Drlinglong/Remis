import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.core.context_local_units import (
    ContextLocalUnitBuilder,
    DeliveryAssignment,
    DeliveryLink,
)
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
from scripts.core.services.context_event_reconciliation_service import EventReconciliationResult
from scripts.core.services.context_synthesis_service import ContextSynthesisService
from scripts.core.services.context_workflow_service import ContextWorkflowService
from scripts.core.services.context_workflow_status_service import ContextWorkflowStatusService
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


class FakeCheckpointPort:
    def __init__(self):
        self.saved = []

    def save_checkpoint(self, task_id, checkpoint):
        self.saved.append((task_id, checkpoint))

    def load_checkpoint(self, task_id):
        for saved_task_id, checkpoint in reversed(self.saved):
            if saved_task_id == task_id:
                return checkpoint
        return None


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

    def publish_draft(
        self, draft_id, metadata, aggregate_ids, syntheses, delivery_memberships=(),
    ):
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
            "delivery_memberships": list(delivery_memberships),
            "contribution_ids": {
                aggregate_id: list(self.repository.aggregates[aggregate_id].contribution_ids)
                for aggregate_id in aggregate_ids
            },
        }
        return release


class FakeMiner:
    def __init__(self, handler):
        self.calls = []

    def extract_structured(
        self,
        source_items,
        *,
        scope,
        game_name,
        target_language,
        reasoning_language,
        core_units=None,
        edge_units=(),
    ):
        del edge_units
        self.calls.append(
            (list(source_items), scope, game_name, target_language, reasoning_language)
        )
        terms = []
        entities = []
        facts = []
        events = []
        relationships = []
        extraction_items = (
            [item for unit in core_units for item in unit.items]
            if core_units is not None else source_items
        )
        for item in extraction_items:
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
        assignments = [
            DeliveryAssignment(
                local_unit_id=unit.unit_id,
                links=[DeliveryLink(
                    event_chain_id="republic-chain",
                    relation="primary_member",
                    confidence=0.9,
                )],
                assignment_state="assigned",
                source_item_ids=[item.source_item_id for item in unit.items],
            )
            for unit in (core_units or ContextLocalUnitBuilder.build(source_items))
        ]
        return StructuredNeologismExtraction(
            terms=terms, entities=entities, facts=facts, events=events,
            relationships=relationships, delivery_assignments=assignments,
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
                    "aggregate_alias": aggregate["aggregate_alias"],
                    "summary": f"Grounded summary for {aggregate['aggregate_type']}.",
                    "evidence_aliases": [
                        aggregate["source_items"][0]["evidence_alias"]
                    ],
                }
                for aggregate in request["aggregates"]
            ]
        })


class FakeReconciler:
    def reconcile(self, local_units, extractions, *, description_language):
        del description_language
        evidence = SourceEvidence(source_item_id=local_units[0].items[0].source_item_id)
        event = EventChainContribution(
            chain_id="republic-chain",
            event="Republic affairs",
            sequence=0,
            evidence=[evidence],
        )
        assignments = [
            DeliveryAssignment(
                local_unit_id=unit.unit_id,
                assignment_state="assigned",
                links=[DeliveryLink(
                    event_chain_id="republic-chain",
                    relation="primary_member",
                    confidence=0.9,
                )],
                source_item_ids=[item.source_item_id for item in unit.items],
            )
            for unit in local_units
        ]
        proposal_resolutions = [
            {
                "proposal_id": f"b{batch_index}_e{event_index}",
                "resolution": "merge_into",
                "final_chain_ids": ["republic-chain"],
            }
            for batch_index, extraction in enumerate(extractions)
            for event_index, _ in enumerate(extraction.events)
        ]
        return EventReconciliationResult(
            events=[event],
            delivery_assignments=assignments,
            diagnostics={"repair_count": 0, "proposal_resolutions": proposal_resolutions},
        )


def _service(repo, candidate_store=None, task_backend=None, handler=None):
    fake_handler = handler or FakeHandler()
    return ContextWorkflowService(
        repo,
        handler_factory=lambda *args, **kwargs: fake_handler,
        candidate_store=candidate_store or FakeCandidateStore(),
        task_backend=task_backend or FakeTaskBackend(),
        miner_factory=FakeMiner,
        synthesizer_factory=ContextSynthesisService,
        reconciler_factory=lambda handler: FakeReconciler(),
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


def test_prompt_example_exposes_all_three_model_stages():
    example = ContextWorkflowService.prompt_example("zh-CN")

    assert "[Local extraction]" in example
    assert "[Global event reconciliation]" in example
    assert "[Archive synthesis]" in example
    assert "Description language: zh-CN" in example


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
    assert ContextWorkflowService.CHUNK_SIZE == 64


def test_context_chunks_use_item_and_source_character_budgets():
    items = [
        SourceItem(
            source_item_id=f"item-{index}",
            relative_path="localisation/english/main.yml",
            item_key=f"key_{index}:0",
            source_order=index,
            source_text="x" * 6,
        )
        for index in range(4)
    ]

    chunks = list(ContextWorkflowService._chunks(items, max_items=3, max_source_chars=13))

    assert [len(chunk) for chunk in chunks] == [2, 2]
    assert [sum(len(item.source_text) for item in chunk) for chunk in chunks] == [12, 12]


def test_context_chunks_keep_an_oversized_source_item_isolated():
    items = [
        SourceItem(
            source_item_id="short",
            relative_path="main.yml",
            item_key="short:0",
            source_order=0,
            source_text="short",
        ),
        SourceItem(
            source_item_id="long",
            relative_path="main.yml",
            item_key="long:0",
            source_order=1,
            source_text="l" * 20,
        ),
        SourceItem(
            source_item_id="tail",
            relative_path="main.yml",
            item_key="tail:0",
            source_order=2,
            source_text="tail",
        ),
    ]

    chunks = list(ContextWorkflowService._chunks(items, max_items=80, max_source_chars=10))

    assert [[item.source_item_id for item in chunk] for chunk in chunks] == [
        ["short"], ["long"], ["tail"]
    ]


def test_context_chunks_keep_adjacent_event_key_family_together_until_budget():
    def item(item_id, key):
        return SourceItem(
            source_item_id=item_id,
            relative_path="localisation/english/events.yml",
            item_key=f"{key}:0",
            source_order=0,
            source_text=item_id,
        )

    items = [
        item("event-name", "event.7130.name"),
        item("event-desc", "event.7130.desc"),
        item("event-options", "event.7130.options"),
        item("next", "event.7131.name"),
    ]

    chunks = list(ContextWorkflowService._chunks(items, max_items=3, max_source_chars=1000))

    assert [[item.source_item_id for item in chunk] for chunk in chunks] == [
        ["event-name", "event-desc", "event-options"], ["next"]
    ]
    assert chunks[0][0].item_key == "event.7130.name:0"


def test_context_chunks_treat_bare_two_segment_event_key_as_its_family_root():
    items = [
        SourceItem(
            source_item_id=f"item-{index}",
            relative_path="localisation/toxoids.yml",
            item_key=key,
            source_order=index,
            source_text=text,
        )
        for index, (key, text) in enumerate([
            ("toxoids.7130:0", "The Toxic God answers."),
            ("toxoids.7130.name:0", "The Answer"),
            ("toxoids.7130.desc:0", "The knight hears the answer."),
            ("toxoids.7131:0", "A different event begins."),
        ])
    ]

    groups = list(ContextWorkflowService._contiguous_groups(items, ContextWorkflowService._grouping_key))

    assert [[item.item_key for item in group] for group in groups] == [
        ["toxoids.7130:0", "toxoids.7130.name:0", "toxoids.7130.desc:0"],
        ["toxoids.7131:0"],
    ]


def test_context_chunk_config_rejects_unsafe_item_override_and_records_safe_budget():
    config = ContextWorkflowService._chunk_config({"max_items": 0, "max_source_chars": "bad"})

    assert config == {"max_items": 64, "max_source_chars": 12000}


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


def test_failed_extraction_retry_reuses_successful_sqlite_batches(tmp_path):
    import sqlite3

    from scripts.core.db_migrations import migrate_main_database
    from scripts.core.repositories.context_analysis_batch_repository import (
        ContextAnalysisBatchRepository,
    )

    root = tmp_path / "mod"
    root.mkdir()
    source = root / "main.yml"
    source.write_text(
        'l_english:\n key_0:0 "Term Zero"\n key_1:0 "Term One"\n key_2:0 "Term Two"\n',
        encoding="utf-8",
    )
    db_path = tmp_path / "projects.sqlite"
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """INSERT INTO projects
               (project_id, name, game_id, source_path, source_language, status)
               VALUES ('project-1', 'Resume Mod', 'vic3', ?, 'english', 'active')""",
            (str(root),),
        )

    class ResumeMiner:
        calls = 0
        failed_once = False

        def __init__(self, handler):
            del handler

        def extract_structured(self, source_items, **kwargs):
            del kwargs
            ResumeMiner.calls += 1
            if source_items[0].item_key == "key_1:0" and not ResumeMiner.failed_once:
                ResumeMiner.failed_once = True
                raise TimeoutError("temporary local-model failure")
            item = source_items[0]
            return StructuredNeologismExtraction(terms=[TermContribution(
                original=item.source_text,
                category="concept",
                suggestion=f"译-{item.source_text}",
                reasoning="直接抽取结果",
                evidence=[SourceEvidence(source_item_id=item.source_item_id)],
            )])

        def review_terms(self, candidates, **kwargs):
            raise AssertionError("complete extraction candidates must not be reviewed")

    batch_repository = ContextAnalysisBatchRepository(str(db_path))
    service = ContextWorkflowService(
        FakeRepository(),
        handler_factory=lambda *args, **kwargs: FakeHandler(),
        candidate_store=FakeCandidateStore(),
        task_backend=FakeTaskBackend(),
        miner_factory=ResumeMiner,
        context_service=FakeContextService(FakeRepository()),
        analysis_batch_repository=batch_repository,
    )

    with pytest.raises(TimeoutError):
        service.run(
            "project-1", [str(source)], str(root), "local", task_id="task-1",
            analysis_config={"max_items": 1},
        )
    with sqlite3.connect(db_path) as connection:
        run_id = connection.execute("SELECT run_id FROM context_analysis_runs").fetchone()[0]
    failed_batches = batch_repository.list_batches(run_id)
    assert [batch.status for batch in failed_batches] == ["succeeded", "failed", "succeeded"]

    result = service.run(
        "project-1", [str(source)], str(root), "local", task_id="task-2",
        analysis_config={"max_items": 1},
    )

    assert ResumeMiner.calls == 4
    assert result["new_terms"] == 3
    assert result["analysis_run_id"]
    assert batch_repository.get_run(result["analysis_run_id"]).status == "complete"
    assert service.get_status("project-1")["checkpoint"]["resume_supported"] is True


def test_terms_only_status_projects_configuration_and_inspection_checkpoint(tmp_path):
    root = tmp_path / "mod"
    root.mkdir()
    source = root / "main.yml"
    source.write_text('l_english:\n key:0 "The Republic appoints a consul."\n', encoding="utf-8")
    task_backend = FakeTaskBackend()
    checkpoint_port = FakeCheckpointPort()
    status_service = ContextWorkflowStatusService(
        task_backend,
        checkpoint_port=checkpoint_port,
    )
    service = ContextWorkflowService(
        FakeRepository(),
        handler_factory=lambda *args, **kwargs: FakeHandler(),
        candidate_store=FakeCandidateStore(),
        task_backend=task_backend,
        status_service=status_service,
        miner_factory=FakeMiner,
        context_service=FakeContextService(FakeRepository()),
    )

    service.run(
        "project-1", [str(source)], str(root), "local", task_id="task-1",
        model_name="local-model", target_lang="ja", description_language="zh-CN",
        analysis_config={"max_items": 2},
    )

    status = service.get_status("project-1")
    assert status["status"] == "completed"
    assert status["source_items"] == 1
    assert status["provider"] == "local"
    assert status["model"] == "local-model"
    assert status["target_lang"] == "ja"
    assert status["description_language"] == "zh-CN"
    assert "affected_source_items" not in status
    assert status["checkpoint"]["resume_supported"] is False
    assert status["checkpoint"]["metadata"]["source_items"] == 1
    assert checkpoint_port.saved
    assert any(
        batch_id == "extracting:1"
        for batch_id in status["checkpoint"]["metadata"]["stages"]["extracting"]["successful_batch_ids"]
    )


def test_review_stage_can_be_skipped_without_fabricating_conflicts(tmp_path):
    root = tmp_path / "mod"
    root.mkdir()
    source = root / "main.yml"
    source.write_text('l_english:\n key:0 "The Republic appoints a consul."\n', encoding="utf-8")

    class NoReviewAdapter:
        def process_terms(self, project_id, parsed_files, extractions, miner, *args, **kwargs):
            return {
                "analysis_scope": "terms_only",
                "new_terms": 0,
                "duplicate_terms": 0,
                "context_release_id": None,
            }

    service = ContextWorkflowService(
        FakeRepository(),
        handler_factory=lambda *args, **kwargs: FakeHandler(),
        candidate_store=FakeCandidateStore(),
        task_backend=FakeTaskBackend(),
        candidate_adapter=NoReviewAdapter(),
        miner_factory=FakeMiner,
        context_service=FakeContextService(FakeRepository()),
    )

    service.run("project-1", [str(source)], str(root), "local", task_id="task-1")

    status = service.get_status("project-1")
    review = status["checkpoint"]["metadata"]["stages"]["reviewing"]
    assert review["skipped"] is True
    assert status["conflict_review_count"] == 0


def test_failed_checkpoint_preserves_prior_success_without_claiming_resume():
    task_backend = FakeTaskBackend()
    checkpoint_port = FakeCheckpointPort()
    status_service = ContextWorkflowStatusService(task_backend, checkpoint_port=checkpoint_port)

    status_service.mark_running(
        "project-1",
        "task-1",
        AnalysisScope.TERMS_ONLY,
        total_files=1,
        source_snapshot_hash="snapshot-1",
        source_items=2,
        total_batches=2,
        workflow_context={
            "analysis_scope": "terms_only",
            "provider": "local",
            "model": "local-model",
            "target_lang": "zh-CN",
            "description_language": "en",
        },
    )
    status_service.record_batch(
        "project-1", "task-1", "extracting", "extracting:1",
        success=True, source_item_ids=["source-1"],
    )
    status_service.record_batch(
        "project-1", "task-1", "extracting", "extracting:2",
        success=False, source_item_ids=["source-2"], error="provider timeout",
    )
    status_service.mark_failed("project-1", "task-1", 1, 0, RuntimeError("provider timeout"))

    status = status_service.get_status("project-1")
    extracting = status["checkpoint"]["metadata"]["stages"]["extracting"]
    assert extracting["successful_batch_ids"] == ["extracting:1"]
    assert extracting["failed_batch_ids"] == ["extracting:2"]
    assert status["successful_batches"] == 1
    assert status["failed_batches"] == 1
    assert status["checkpoint"]["available"] is True
    assert status["checkpoint"]["resume_supported"] is False


def test_context_progress_separates_current_stage_from_overall_workflow():
    task_backend = FakeTaskBackend()
    status_service = ContextWorkflowStatusService(
        task_backend, checkpoint_port=FakeCheckpointPort(),
    )
    status_service.mark_running(
        "project-1", "task-1", AnalysisScope.NARRATIVE_CONTEXT,
        total_files=1, source_snapshot_hash="snapshot-1",
        source_items=339, total_batches=6,
    )

    for index in range(1, 7):
        status_service.record_batch(
            "project-1", "task-1", "extracting", f"extracting:{index}",
            success=True, source_item_ids=[f"source-{index}"],
        )

    extracting = status_service.get_status("project-1")
    assert extracting["current_batch"] == 6
    assert extracting["total_batches"] == 6
    assert extracting["progress"]["percent"] == 20

    status_service.begin_stage("project-1", "task-1", "reviewing", 1)
    status_service.record_batch(
        "project-1", "task-1", "reviewing", "reviewing:1", success=True,
    )
    status_service.begin_stage("project-1", "task-1", "aggregating", 1)
    status_service.record_batch(
        "project-1", "task-1", "aggregating", "aggregating:1", success=True,
    )
    status_service.begin_stage("project-1", "task-1", "synthesizing", 2)
    status_service.record_batch(
        "project-1", "task-1", "synthesizing", "synthesizing:1",
        success=False, error="invalid json",
    )
    status_service.mark_failed(
        "project-1", "task-1", 1, 0, RuntimeError("invalid json"),
    )

    failed = status_service.get_status("project-1")
    assert failed["status"] == "failed"
    assert failed["progress"]["percent"] == 70
    assert failed["checkpoint"]["metadata"]["failed_stage"] == "synthesizing"
    stages = failed["checkpoint"]["metadata"]["stages"]
    assert len(stages["extracting"]["successful_batch_ids"]) == 6
    assert len(stages["reviewing"]["successful_batch_ids"]) == 1
    assert len(stages["aggregating"]["successful_batch_ids"]) == 1


def test_narrative_release_has_metadata_traceability_summary_and_parent_diff(tmp_path):
    root = tmp_path / "mod"
    root.mkdir()
    source = root / "main.yml"
    source.write_text(
        'l_english:\n first_key:0 "The Republic appoints a consul."\n second_key:0 "The Republic protects a gate."\n',
        encoding="utf-8",
    )
    repo = FakeRepository()
    handler = FakeHandler()
    service = _service(repo, handler=handler)

    first = service.run(
        "project-1", [str(source)], str(root), "local", task_id="task-1",
        analysis_scope=AnalysisScope.NARRATIVE_CONTEXT, model_name="fake-model",
        description_language="zh-CN",
    )
    assert first["context_release_id"] == "release-1"
    release = repo.releases["release-1"]
    assert release.metadata.provider_id == "local"
    assert release.metadata.model_id == "fake-model"
    assert release.metadata.schema_version == "context-v3"
    assert release.metadata.prompt_version == "context-archive-v6"
    assert release.metadata.analysis_config["description_language"] == "zh-CN"
    assert "Simplified Chinese (zh-CN)" in handler.calls[0][0]["content"]
    assert any(
        update[1].get("fields", {}).get("stage_code") == "synthesizing"
        for update in service.task_backend.updates
    )
    assert release.metadata.parent_release_id is None
    assert any(
        item.context_key == "project:summary"
        for item in service.context_service.snapshots["release-1"]["syntheses"]
    )
    assert first["delivery_membership_count"] == 2
    report = first["analysis_report"]
    assert report["input_and_chunking"]["source_items"] == 2
    assert report["input_and_chunking"]["local_units"] == 2
    assert report["unit_assignment_integrity"]["missing"] == []
    assert report["unit_assignment_integrity"]["one_to_one_after_repair"] is True
    assert report["coverage_and_contamination"]["theme_related_injection_count"] == 0
    assert report["coverage_and_contamination"]["parent_story_automatic_inheritance_count"] == 0
    assert len(service.context_service.snapshots["release-1"]["delivery_memberships"]) == 2
    first_sources = set(repo.sources)

    source.write_text('l_english:\n first_key:0 "The Republic appoints a consul."\n', encoding="utf-8")
    second = service.run(
        "project-1", [str(source)], str(root), "local", task_id="task-2",
        analysis_scope=AnalysisScope.NARRATIVE_CONTEXT, model_name="fake-model",
        description_language="zh-CN",
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
                    "aggregate_alias": "a0",
                    "summary": "The Republic appoints a consul.",
                    "evidence_aliases": ["e0"],
                }]
            })

    handler = RepairHandler()
    result = ContextSynthesisService(handler).synthesize(
        [aggregate], {contribution.contribution_id: contribution}, {source.source_item_id: source}
    )

    assert len(handler.calls) == 2
    assert len(handler.calls[1]) == 3
    assert handler.calls[1][-1]["role"] == "user"
    repair_instruction = handler.calls[1][-1]["content"]
    assert '"syntheses":[' in repair_instruction
    assert "Do not create entities, events, or project_summary" in repair_instruction
    assert repair_instruction.endswith("Invalid response excerpt: not-json")
    assert result[0].content["evidence_source_item_ids"] == ["source-1"]


def test_synthesis_prompt_example_uses_the_real_contract_and_requested_language():
    example = ContextSynthesisService.prompt_example("zh-CN")

    assert "System message:" in example
    assert "User message:" in example
    assert '"syntheses":[' in example
    assert "Simplified Chinese (zh-CN)" in example
    assert '"aggregate_alias": "a0"' in example
    assert "example_l_english.yml::example.1.desc" in example


def test_synthesis_repairs_categorized_object_shape_with_explicit_flat_contract():
    source = ContextSourceItem(
        source_item_id="source-1", project_id="project-1", source_type="localization",
        source_ref="main.yml::0:key", content="The Republic appoints a consul.",
        content_hash="hash-1",
    )
    contribution = ContextContribution(
        contribution_id="contribution-1", source_item_id=source.source_item_id,
        contribution_type="fact", subject_key="entity:republic",
        payload={"evidence": [{"source_item_id": source.source_item_id}]},
        provenance="text_inferred",
    )
    aggregate = ContextAggregate(
        aggregate_id="aggregate-1", project_id="project-1", aggregate_type="entity",
        aggregate_key="entity:republic", contribution_ids=[contribution.contribution_id],
    )

    class CategorizedShapeHandler:
        def __init__(self):
            self.calls = []

        def generate_with_messages(self, messages, temperature=0.0):
            self.calls.append(messages)
            if len(self.calls) == 1:
                system_prompt = messages[0]["content"]
                assert '"syntheses":[' in system_prompt
                assert "syntheses value MUST be a JSON array" in system_prompt
                return json.dumps({
                    "syntheses": {
                        "entities": [{
                            "aggregate_alias": "a0",
                            "summary": "The Republic appoints a consul.",
                            "evidence_aliases": ["e0"],
                        }],
                        "events": [],
                        "project_summary": "A republican project.",
                    }
                })
            repair_prompt = messages[-1]["content"]
            assert '"syntheses":[' in repair_prompt
            assert "Do not create entities, events, or project_summary" in repair_prompt
            return json.dumps({
                "syntheses": [{
                    "aggregate_alias": "a0",
                    "summary": "The Republic appoints a consul.",
                    "evidence_aliases": ["e0"],
                }]
            })

    handler = CategorizedShapeHandler()
    result = ContextSynthesisService(handler).synthesize(
        [aggregate],
        {contribution.contribution_id: contribution},
        {source.source_item_id: source},
    )

    assert len(handler.calls) == 2
    assert result[0].content["summary"] == "The Republic appoints a consul."


def test_synthesis_keeps_real_ids_out_of_model_contract_and_maps_aliases_back():
    source_id = "source-item-0d4f2ecb-0d99-4d48-a29d-8cf44f6d06f7"
    aggregate_id = "aggregate-29a013eb-8770-40ef-81e3-601ec7044fad"
    context_key = "entity:the-trickster:internal-context-key"
    source = ContextSourceItem(
        source_item_id=source_id, project_id="project-1", source_type="localization",
        source_ref="main.yml::0:key", content="The Trickster deceives the council.",
        content_hash="hash-1",
    )
    contribution = ContextContribution(
        contribution_id="contribution-with-another-long-internal-id",
        source_item_id=source_id,
        contribution_type="fact",
        subject_key=context_key,
        payload={
            "subject": "The Trickster",
            "predicate": "deceives",
            "object": "the council",
            "evidence": [{"source_item_id": source_id}],
        },
        provenance="text_inferred",
    )
    aggregate = ContextAggregate(
        aggregate_id=aggregate_id, project_id="project-1", aggregate_type="entity",
        aggregate_key=context_key, contribution_ids=[contribution.contribution_id],
    )

    class AliasHandler:
        def __init__(self):
            self.messages = None
            self.schema = None

        def generate_structured_with_messages(
            self, messages, *, schema, schema_name, temperature=0.0,
        ):
            self.messages = messages
            self.schema = schema
            request = json.loads(messages[-1]["content"])
            item = request["aggregates"][0]
            return json.dumps({
                "syntheses": [{
                    "aggregate_alias": item["aggregate_alias"],
                    "summary": "The Trickster deceives the council.",
                    "evidence_aliases": [item["source_items"][0]["evidence_alias"]],
                }]
            })

    handler = AliasHandler()
    result = ContextSynthesisService(handler).synthesize(
        [aggregate], {contribution.contribution_id: contribution}, {source_id: source},
    )

    model_contract = json.dumps(
        {"messages": handler.messages, "schema": handler.schema}, ensure_ascii=False,
    )
    assert aggregate_id not in model_contract
    assert context_key not in model_contract
    assert source_id not in model_contract
    assert contribution.contribution_id not in model_contract
    assert result[0].aggregate_id == aggregate_id
    assert result[0].context_key == context_key
    assert result[0].content["evidence_source_item_ids"] == [source_id]


def test_synthesis_bisects_truncated_batch_without_replaying_large_fragment():
    source = ContextSourceItem(
        source_item_id="source-1", project_id="project-1", source_type="localization",
        source_ref="main.yml::0:key", content="The Trickster deceives the council.",
        content_hash="hash-1",
    )
    contribution = ContextContribution(
        contribution_id="contribution-1", source_item_id=source.source_item_id,
        contribution_type="fact", subject_key="entity:the-trickster",
        payload={"evidence": [{"source_item_id": source.source_item_id}]},
        provenance="text_inferred",
    )
    aggregates = [
        ContextAggregate(
            aggregate_id=f"aggregate-{index}", project_id="project-1",
            aggregate_type="entity", aggregate_key=f"entity:the-trickster:{index}",
            contribution_ids=[contribution.contribution_id],
        )
        for index in range(4)
    ]

    class TruncatingHandler:
        TRUNCATED_FRAGMENT = "unfinished-output-fragment" * 300

        def __init__(self):
            self.calls = []

        def generate_with_messages(self, messages, temperature=0.0):
            self.calls.append(messages)
            request = json.loads(messages[-1]["content"])
            if len(request["aggregates"]) > 1:
                return '{"syntheses":[{"aggregate_alias":"a0","summary":"' + self.TRUNCATED_FRAGMENT
            aggregate = request["aggregates"][0]
            return json.dumps({
                "syntheses": [{
                    "aggregate_alias": aggregate["aggregate_alias"],
                    "summary": "Grounded Trickster summary.",
                    "evidence_aliases": [aggregate["source_items"][0]["evidence_alias"]],
                }]
            })

    handler = TruncatingHandler()
    result = ContextSynthesisService(handler).synthesize(
        aggregates,
        {contribution.contribution_id: contribution},
        {source.source_item_id: source},
    )

    assert len(handler.calls) == 7
    assert [item.aggregate_id for item in result] == [item.aggregate_id for item in aggregates]
    assert all(
        TruncatingHandler.TRUNCATED_FRAGMENT[:100] not in json.dumps(messages)
        for messages in handler.calls
    )


def test_synthesis_batches_large_aggregate_sets():
    source = ContextSourceItem(
        source_item_id="source-1", project_id="project-1", source_type="localization",
        source_ref="main.yml::0:key", content="The Republic appoints a consul.", content_hash="hash-1",
    )
    contribution = ContextContribution(
        contribution_id="contribution-1", source_item_id="source-1", contribution_type="fact",
        subject_key="entity:republic", payload={"evidence": [{"source_item_id": "source-1"}]},
        provenance="text_inferred",
    )
    aggregates = [
        ContextAggregate(
            aggregate_id=f"aggregate-{index}", project_id="project-1", aggregate_type="entity",
            aggregate_key=f"entity:republic:{index}", contribution_ids=[contribution.contribution_id],
        )
        for index in range(ContextSynthesisService.MAX_AGGREGATES_PER_CALL + 1)
    ]
    handler = FakeHandler()

    result = ContextSynthesisService(handler).synthesize(
        aggregates,
        {contribution.contribution_id: contribution},
        {source.source_item_id: source},
    )

    assert len(handler.calls) == 2
    assert [item.aggregate_id for item in result] == [item.aggregate_id for item in aggregates]


def test_synthesis_batches_by_payload_budget_before_count_cap():
    sources = {}
    contributions = {}
    aggregates = []
    for index in range(3):
        source = ContextSourceItem(
            source_item_id=f"source-{index}", project_id="project-1",
            source_type="localization", source_ref=f"main.yml::{index}:key",
            content="Grounded evidence. " * 1000, content_hash=f"hash-{index}",
        )
        contribution = ContextContribution(
            contribution_id=f"contribution-{index}", source_item_id=source.source_item_id,
            contribution_type="fact", subject_key=f"entity:{index}",
            payload={"evidence": [{"source_item_id": source.source_item_id}]},
            provenance="text_inferred",
        )
        aggregate = ContextAggregate(
            aggregate_id=f"aggregate-{index}", project_id="project-1",
            aggregate_type="entity", aggregate_key=f"entity:{index}",
            contribution_ids=[contribution.contribution_id],
        )
        sources[source.source_item_id] = source
        contributions[contribution.contribution_id] = contribution
        aggregates.append(aggregate)
    handler = FakeHandler()

    result = ContextSynthesisService(handler).synthesize(aggregates, contributions, sources)

    assert len(handler.calls) == 2
    assert all(
        len(json.loads(messages[-1]["content"])["aggregates"]) < len(aggregates)
        for messages in handler.calls
    )
    assert [item.aggregate_id for item in result] == [item.aggregate_id for item in aggregates]
