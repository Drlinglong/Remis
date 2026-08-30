from types import SimpleNamespace

import pytest

from scripts.core.context_local_units import DeliveryAssignment, DeliveryLink
from scripts.core.neologism_extraction import StructuredNeologismExtraction
from scripts.core.services.context_delivery_membership_service import (
    ContextDeliveryMembershipError,
    ContextDeliveryMembershipService,
)
from scripts.core.services.context_workflow_service import ContextWorkflowService
from scripts.schemas.context import ContextAggregate, ContextSourceItem


def _aggregate(key="event:known"):
    return ContextAggregate(
        aggregate_id="aggregate-1",
        project_id="project-1",
        aggregate_type="event",
        aggregate_key=key,
        contribution_ids=["contribution-1"],
    )


def _source(source_id="source-1"):
    return ContextSourceItem(
        source_item_id=source_id,
        project_id="project-1",
        source_type="localization",
        source_ref="localisation/english/main_l_english.yml::main",
        content="Main entry",
        content_hash="hash",
    )


def _extraction(relation, event_chain_id="known", source_item_ids=None):
    return StructuredNeologismExtraction(
        delivery_assignments=[DeliveryAssignment(
            local_unit_id="unit_0",
            assignment_state="assigned",
            links=[DeliveryLink(
                event_chain_id=event_chain_id,
                relation=relation,
                confidence=0.9,
            )],
            source_item_ids=source_item_ids or ["source-1"],
        )],
    )


def test_unknown_primary_membership_target_aborts_publication():
    result = ContextDeliveryMembershipService.build(
        [_extraction("primary_member", event_chain_id="missing")],
        [_aggregate()],
        {"source-1": _source()},
        expected_local_unit_ids=["unit_0"],
    )

    assert result.has_blockers is True
    assert result.memberships == ()
    assert result.diagnostics["blocking"] is True
    assert result.dropped_edges[0]["blocking"] is True
    assert result.dropped_edges[0]["code"] == "unknown_primary_membership_target"
    error = ContextDeliveryMembershipError(result)
    assert error.detail["code"] == "context_delivery_membership_incomplete"
    assert error.detail["membership"]["diagnostics"]["blocking"] is True


def test_unknown_source_aborts_publication():
    result = ContextDeliveryMembershipService.build(
        [_extraction("supporting_context", source_item_ids=["missing-source"])],
        [_aggregate()],
        {"source-1": _source()},
        expected_local_unit_ids=["unit_0"],
    )

    assert result.has_blockers is True
    assert result.diagnostics["unknown_source_item_count"] == 1
    assert result.dropped_edges[0]["code"] == "unknown_source_item"


def test_theme_related_is_audited_not_delivered():
    result = ContextDeliveryMembershipService.build(
        [_extraction("theme_related")],
        [_aggregate()],
        {"source-1": _source()},
        expected_local_unit_ids=["unit_0"],
    )

    assert result.has_blockers is False
    assert result.memberships == ()
    assert result.diagnostics["theme_related_count"] == 1
    assert result.dropped_edges[0]["code"] == "theme_related_not_delivered"
    assert result.dropped_edges[0]["blocking"] is False


def test_context_workflow_does_not_publish_blocking_membership_result(monkeypatch):
    result = ContextDeliveryMembershipService.build(
        [_extraction("primary_member", event_chain_id="missing")],
        [_aggregate()],
        {"source-1": _source()},
        expected_local_unit_ids=["unit_0"],
    )
    published_aggregates = []

    class Assembler:
        @staticmethod
        def persist_sources(*_args):
            return {"source-1": _source()}

        @staticmethod
        def persist_contributions(*_args):
            return {"contribution-1": object()}

        @staticmethod
        def build_aggregates(*_args):
            return [_aggregate()]

    service = object.__new__(ContextWorkflowService)
    service.release_assembler = Assembler()
    service.repository = type(
        "Repository",
        (),
        {"save_aggregate": lambda _self, aggregate: published_aggregates.append(aggregate)},
    )()
    monkeypatch.setattr(
        ContextDeliveryMembershipService,
        "build",
        lambda *_args, **_kwargs: result,
    )

    with pytest.raises(ContextDeliveryMembershipError):
        service._finish_context(
            project_id="project-1",
            parsed_files=[],
            snapshot=SimpleNamespace(source_snapshot_hash="hash"),
            diff=SimpleNamespace(),
            parent=None,
            local_units=[],
            extractions=[],
            api_provider="local",
            model_name=None,
            upstream_version=None,
            analysis_config=None,
            description_language="en",
            chunk_config={},
            task_id=None,
            concurrency=1,
            analysis_report={},
            governance=SimpleNamespace(available=False),
            usage_ledger=SimpleNamespace(),
            expected_local_unit_ids=["unit_0"],
        )

    assert published_aggregates == []
