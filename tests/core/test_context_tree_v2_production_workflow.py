from types import SimpleNamespace

from scripts.core.services.context_model_usage import ContextModelUsageLedger
from scripts.core.services.context_tree_v2_production_workflow import (
    ContextTreeV2ProductionWorkflowService,
)


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
    def begin_stage(self, *args, **kwargs):
        pass

    def record_batch(self, *args, **kwargs):
        pass

    def complete_stage(self, *args, **kwargs):
        pass


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
