from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import AnalysisScope, SourceItem
from scripts.core.services.context_chunking_policy import ContextUnitChunk
from scripts.core.services.context_model_usage import ContextModelUsageLedger
from scripts.core.services.context_tree_v2_contract import ContextTreeV2Extraction
from scripts.core.services.context_tree_v2_extraction_execution_service import (
    ContextTreeV2ExtractionExecutionService,
)
from scripts.core.services.context_tree_v2_production_workflow import (
    ContextTreeV2ProductionWorkflowService,
)
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


class CandidateStore:
    def __init__(self):
        self.items = []

    def load_candidates(self, project_id):
        return [item for item in self.items if item.project_id == project_id]

    def save_candidates(self, project_id, candidates):
        self.items = list(candidates)


class TreeRepository:
    def __init__(self):
        self.published = []

    def save_tree(self, tree):
        return tree

    def create_draft(self, project_id, tree_id):
        return SimpleNamespace(draft_id="draft-1", project_id=project_id, tree_id=tree_id)

    def validate_draft(self, project_id, draft_id):
        return SimpleNamespace(valid=True, model_dump=lambda **kwargs: {"valid": True})

    def publish_draft(self, project_id, draft_id, idempotency_key):
        self.published.append((project_id, draft_id, idempotency_key))
        return {"release_id": "release-1"}


class StatusService:
    def __init__(self):
        self.batches = []
        self.completed = []

    def begin_stage(self, *args, **kwargs):
        pass

    def record_batch(self, *args, **kwargs):
        self.batches.append((args, kwargs))

    def complete_stage(self, *args, **kwargs):
        self.completed.append((args, kwargs))


class Checkpoints:
    def __init__(self, restored=None):
        self.restored = dict(restored or {})
        self.saved = []

    def restore_extraction(self, _run, index, _source_ids):
        return self.restored.get(index)

    def save_extraction(self, _run, index, source_ids, result):
        self.saved.append((index, tuple(source_ids), result))


def _chunks(count):
    chunks = []
    for index in range(count):
        item = SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/story.yml",
            item_key=f"story.{index}.title",
            source_order=index,
            source_text=f"Story event {index}",
        )
        unit = LocalTextUnit(
            unit_id=f"unit_{index}", unit_key=f"story::{index}", items=(item,),
        )
        chunks.append(ContextUnitChunk(
            core_units=(unit,), edge_units=(), chunk_index=index, chunk_count=count,
        ))
    return chunks


def _persist(digest_status):
    repository = TreeRepository()
    service = ContextTreeV2ProductionWorkflowService(
        handler_factory=lambda *args, **kwargs: None,
        tree_repository=repository,
        candidate_store=CandidateStore(),
        status_service=StatusService(),
    )
    eligible = SimpleNamespace(
        candidate_id="entity-1",
        canonical_name="Knight",
        aliases=(),
        is_digest_eligible=True,
    )
    digests = SimpleNamespace(
        digests=[SimpleNamespace(candidate_id="entity-1", digest_status=digest_status)],
        call_records=[],
        evidence_bundles=[],
    )
    result = service._persist_archive(
        SimpleNamespace(tree_id="tree-1", unresolved_references=[]),
        SimpleNamespace(model_calls={}),
        SimpleNamespace(candidates=[eligible], report={}),
        digests,
        project_id="project-1",
        task_id="task-1",
        source_language="en",
        target_language="zh-CN",
        description_language="zh-CN",
        term_result=SimpleNamespace(terms=[]),
        source_items=[SimpleNamespace(source_item_id="source-1")],
        local_units=[],
        duplicate_index={},
        usage_ledger=ContextModelUsageLedger(),
    )
    return result, repository


def test_incomplete_required_entity_digest_cannot_publish():
    result, repository = _persist("failed")

    assert result["publication_status"] == "review_required"
    assert result["context_release_id"] is None
    assert result["analysis_report"]["required_entity_digests_complete"] is False
    assert repository.published == []


def test_complete_required_entity_digest_can_publish_after_tree_validation():
    result, repository = _persist("complete")

    assert result["publication_status"] == "published"
    assert result["context_release_id"] == "release-1"
    assert repository.published == [
        ("project-1", "draft-1", "context-tree-v2:tree-1"),
    ]


def test_v2_extraction_reuses_checkpoints_and_runs_pending_batches_concurrently():
    barrier = Barrier(2)
    restored = ContextTreeV2Extraction(diagnostics={"source_id": "source-0"})
    checkpoints = Checkpoints({0: restored})
    status = StatusService()

    class ProbeExtractionService:
        def __init__(self, _handler):
            pass

        def extract_structured(self, items, **_kwargs):
            barrier.wait(timeout=2)
            return ContextTreeV2Extraction(
                diagnostics={"source_id": items[0].source_item_id},
            )

    execution = ContextTreeV2ExtractionExecutionService(
        handler_factory=lambda *_args, **_kwargs: SimpleNamespace(),
        checkpoints=checkpoints,
        status_service=status,
        usage_ledger=ContextModelUsageLedger(),
    )
    target = (
        "scripts.core.services.context_tree_v2_extraction_execution_service."
        "ContextTreeV2ExtractionService"
    )
    with patch(target, ProbeExtractionService):
        result = execution.execute(
            _chunks(3),
            scope=AnalysisScope.NARRATIVE_CONTEXT,
            game_name="Stellaris",
            project_id="project-1",
            task_id="task-1",
            target_language="zh-CN",
            reasoning_language="zh-CN",
            analysis_run=SimpleNamespace(run_id="run-1"),
            api_provider="openrouter",
            model_name="openai/gpt-5.6-luna",
            concurrency=2,
        )

    assert [item.diagnostics["source_id"] for item in result] == [
        "source-0", "source-1", "source-2",
    ]
    assert sorted(saved[0] for saved in checkpoints.saved) == [1, 2]
    assert status.batches[0][0][3] == "tree-v2-extraction-0"
    assert status.batches[0][1]["resumed"] is True
    assert status.completed == [(("project-1", "task-1", "extracting"), {})]


def test_v2_extraction_reuses_the_runtime_snapshot_for_each_pending_batch():
    checkpoints = Checkpoints()
    status = StatusService()
    calls = []

    class ProbeExtractionService:
        def __init__(self, _handler):
            pass

        def extract_structured(self, items, **_kwargs):
            return ContextTreeV2Extraction(
                diagnostics={"source_id": items[0].source_item_id},
            )

    execution = ContextTreeV2ExtractionExecutionService(
        handler_factory=lambda provider, model_name=None, **kwargs: calls.append(
            (provider, model_name, kwargs)
        ) or SimpleNamespace(),
        checkpoints=checkpoints,
        status_service=status,
        usage_ledger=ContextModelUsageLedger(),
    )
    runtime = ProviderRuntimeSnapshot(
        selection_id="profile-1", adapter_id="your_favourite_api",
        display_name="Provider A", model_id="model-a",
        config={"base_url": "https://provider-a.example"},
    )
    target = (
        "scripts.core.services.context_tree_v2_extraction_execution_service."
        "ContextTreeV2ExtractionService"
    )
    with patch(target, ProbeExtractionService):
        execution.execute(
            _chunks(2), scope=AnalysisScope.NARRATIVE_CONTEXT,
            game_name="Stellaris", project_id="project-1", task_id="task-1",
            target_language="zh-CN", reasoning_language="zh-CN",
            analysis_run=SimpleNamespace(run_id="run-1"),
            api_provider="legacy-provider", model_name="legacy-model",
            concurrency=2, runtime=runtime,
        )

    assert len(calls) == 2
    assert all(call[0:2] == ("your_favourite_api", "model-a") for call in calls)
    assert all(call[2]["provider_config_snapshot"] == runtime.config for call in calls)
