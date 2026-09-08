from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_route_resolver import apply_delivery_routes
from scripts.core.services.context_research_shard_memo import (
    CollectedShardUnit,
    ShardMemoCollection,
)


def _findings(*, units=("unit_1",), reference_units=(), include_archive=True):
    return ContextResearchFindings.model_validate({
        "archive_narratives": ([{
            "narrative_id": "lore",
            "summary": "背景仍应保留。",
            "evidence": [{"source_item_ids": ["source-1"]}],
        }] if include_archive else []),
        "entities": [{
            "entity_id": "person", "name": "人物", "entity_type": "person",
            "summary": "实体仍应保留。",
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
        "event_chains": [{
            "chain_id": "chain", "sequence": 1, "event": "事件。",
            "local_unit_ids": list(units),
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
        "reference_assets": [{
            "asset_id": f"asset-{unit}", "name": "静态项",
            "local_unit_id": unit,
            "evidence": [{"source_item_ids": ["source-1"]}],
        } for unit in reference_units],
    })


def _unit(unit_id, findings, *, content_role, delivery_route):
    return CollectedShardUnit(
        local_unit_id=unit_id,
        owner_shard_id="shard-1",
        owner_role="event_investigator",
        disposition="modeled",
        findings=findings,
        content_role=content_role,
        delivery_route=delivery_route,
        confidence="medium",
        evidence=("source-1",),
    )


def test_event_delivery_drops_reference_but_keeps_archive_and_entity():
    findings = _findings(reference_units=("unit_1",))
    collection = ShardMemoCollection(
        findings=findings,
        units=(_unit(
            "unit_1", findings, content_role="event_narrative", delivery_route="event",
        ),),
    )

    result = apply_delivery_routes(collection, findings)

    assert result.event_chains[0].local_unit_ids == ("unit_1",)
    assert result.reference_assets == ()
    assert result.archive_narratives
    assert result.entities
    assert result.diagnostics["route_resolution"]["conflict_count_after"] == 0


def test_none_delivery_publishes_neither_route_claim():
    findings = _findings(reference_units=("unit_1",))
    collection = ShardMemoCollection(
        findings=findings,
        units=(_unit(
            "unit_1", findings, content_role="background_narrative", delivery_route="none",
        ),),
    )

    result = apply_delivery_routes(collection, findings)

    assert result.event_chains == ()
    assert result.reference_assets == ()
    assert result.archive_narratives
    resolution = result.diagnostics["route_resolution"]
    assert resolution["content_roles"] == {"unit_1": "background_narrative"}
    assert resolution["delivery_routes"] == {"unit_1": "none"}


def test_event_members_are_filtered_per_unit_and_single_reference_wins():
    findings = _findings(
        units=("unit_1", "unit_2"), reference_units=("unit_2",),
    )
    collection = ShardMemoCollection(
        findings=findings,
        units=(
            _unit(
                "unit_1", findings,
                content_role="event_narrative", delivery_route="event",
            ),
            _unit(
                "unit_2", findings,
                content_role="static_reference", delivery_route="reference",
            ),
        ),
    )

    result = apply_delivery_routes(collection, findings)

    assert result.event_chains[0].local_unit_ids == ("unit_1",)
    assert [item.local_unit_id for item in result.reference_assets] == ["unit_2"]


def test_delivery_route_is_independent_of_content_role():
    findings = _findings(reference_units=("unit_1",))
    collection = ShardMemoCollection(
        findings=findings,
        units=(_unit(
            "unit_1", findings,
            content_role="background_narrative", delivery_route="reference",
        ),),
    )

    result = apply_delivery_routes(collection, findings)

    assert result.event_chains == ()
    assert result.reference_assets
    assert result.archive_narratives
