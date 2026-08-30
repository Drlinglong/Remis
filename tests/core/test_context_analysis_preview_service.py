from types import SimpleNamespace

from scripts.core.services.context_analysis_preview_service import (
    ContextAnalysisPreviewService,
)
from scripts.schemas.context import ContextAggregate


def _run(**updates):
    values = {
        "run_id": "run-1",
        "task_id": "task-1",
        "project_id": "project-1",
        "source_snapshot_hash": "snapshot-1",
        "analysis_scope": {"mode": "narrative_context"},
        "config": {
            "provider": "openrouter",
            "model": "openai/gpt-5.6-luna",
            "prompt_version": "context-archive-v9",
            "schema_version": "context-v4",
        },
        "phase": "synthesis",
        "status": "failed",
        "publication_status": "not_published",
        "created_at": "2026-08-04T00:00:00+00:00",
        "updated_at": "2026-08-04T01:00:00+00:00",
    }
    values.update(updates)
    return SimpleNamespace(**values)


def _batch(phase, payload, *, status="succeeded", batch_index=0):
    return SimpleNamespace(
        phase=phase,
        payload=payload,
        status=status,
        batch_index=batch_index,
    )


class FakeRepository:
    def list_aggregates(self, project_id):
        assert project_id == "project-1"
        return [
            ContextAggregate(
                aggregate_id="entity-1",
                project_id=project_id,
                aggregate_type="entity",
                aggregate_key="entity:toxic god",
                payload={
                    "canonical_display_name": "Toxic God",
                    "aliases": ["The Toxic God", "Toxic God"],
                    "candidate_kind": "entity",
                    "tier": "core",
                    "summary_eligible": True,
                    "audit_only": False,
                    "mention_count": 8,
                    "local_unit_coverage": 4,
                },
                contribution_ids=["contribution-1"],
            ),
            ContextAggregate(
                aggregate_id="event-1",
                project_id=project_id,
                aggregate_type="event",
                aggregate_key="event:chain_toxic_god",
                payload={"active_contribution_count": 2},
                contribution_ids=["contribution-2"],
            ),
            ContextAggregate(
                aggregate_id="project-summary",
                project_id=project_id,
                aggregate_type="project",
                aggregate_key="project:summary",
                contribution_ids=["contribution-3"],
            ),
        ]


class FakeBatchRepository:
    def __init__(self):
        self.run = _run()
        self.batches = [
            _batch("aggregation", {
                "catalog": {"final_chains": [{
                    "chain_id": "chain_toxic_god",
                    "event": "The order seeks the Toxic God.",
                    "consequence": "The quest continues.",
                    "participants": ["Toxic God", "Order"],
                    "parent_story_id": None,
                    "evidence_unit_ids": ["unit-1"],
                }]},
            }),
            _batch("aggregation", {
                "assignment_batch": {"assignments": [{
                    "local_unit_id": "unit-1",
                    "links": [{
                        "event_chain_id": "chain_toxic_god",
                        "relation": "primary_member",
                    }],
                }, {
                    "local_unit_id": "unit-2",
                    "links": [{
                        "event_chain_id": "chain_toxic_god",
                        "relation": "supporting_context",
                    }],
                }]},
            }, batch_index=1),
            _batch("synthesis", {"syntheses": [{
                "aggregate_id": "entity-1",
                "content": {
                    "summary": "A godlike toxic entity.",
                    "evidence_source_item_ids": ["source-1"],
                },
            }, {
                "aggregate_id": "event-1",
                "content": {
                    "summary": "The order begins its quest.",
                    "evidence_source_item_ids": ["source-2"],
                },
            }, {
                "aggregate_id": "project-summary",
                "content": {
                    "summary": "Project summary.",
                    "evidence_source_item_ids": ["source-3"],
                },
            }]}),
        ]

    def list_runs(self, project_id):
        return [self.run] if project_id == "project-1" else []

    def list_batches(self, run_id, phase=None):
        assert run_id == "run-1"
        return [batch for batch in self.batches if phase is None or batch.phase == phase]


def test_latest_preview_exposes_failed_run_without_claiming_publication():
    preview = ContextAnalysisPreviewService(
        FakeRepository(),
        FakeBatchRepository(),
    ).latest("project-1")

    assert preview is not None
    assert preview.published is False
    assert preview.warning_code == "unpublished_analysis_preview"
    assert preview.run.status == "failed"
    assert preview.run.model_id == "openai/gpt-5.6-luna"
    assert preview.counts == {
        "entities": 1,
        "events": 1,
        "syntheses": 3,
        "entity_summaries": 1,
        "event_summaries": 1,
        "core": 1,
        "secondary": 0,
        "incidental": 0,
        "not_recorded": 0,
        "audit_only": 0,
    }
    event, entity = preview.entries
    assert event.aggregate_key == "event:chain_toxic_god"
    assert event.payload["delivery_coverage"] == {
        "local_unit_coverage": 2,
        "primary_member": 1,
        "supporting_context": 1,
        "theme_related": 0,
    }
    assert entity.label == "Toxic God"
    assert entity.summary == "A godlike toxic entity."


def test_latest_preview_requires_aggregation_and_synthesis_checkpoints():
    batches = FakeBatchRepository()
    batches.batches = [
        _batch("aggregation", {"catalog": {"final_chains": []}}),
    ]

    assert ContextAnalysisPreviewService(FakeRepository(), batches).latest("project-1") is None
