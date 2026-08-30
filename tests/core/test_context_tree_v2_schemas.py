import pytest
from pydantic import ValidationError

from scripts.schemas.context_tree_v2 import (
    ChunkEdgeMetadata,
    EntityDigest,
    EntityDigestSegment,
    LocalFragmentCard,
    OrderedFragmentEdge,
    PrePublicationValidationIssue,
    PrePublicationValidationRequest,
    PrePublicationValidationResult,
    ReadTreeResponse,
    SiblingGroup,
    SourceEvidenceReference,
    Story,
    TreeDraftOverrideOperation,
    UnitRoute,
    UnresolvedReference,
)


def _evidence(local_unit_id: str = "unit-1") -> SourceEvidenceReference:
    return SourceEvidenceReference(
        source_item_id="source-1",
        local_unit_id=local_unit_id,
        source_ref="events.yml:12",
        item_key="event.one.desc",
        excerpt="The local source evidence.",
    )


def _card() -> LocalFragmentCard:
    return LocalFragmentCard(
        fragment_id="fragment-1",
        summary="The first local event fragment.",
        unit_ids=["unit-1"],
        continuation_clues=["The next chunk may continue the event."],
        boundary_includes="The event introduction.",
        boundary_excludes="A separate aftermath.",
        edge_metadata=ChunkEdgeMetadata(
            chunk_id="chunk-1",
            touches_chunk_end=True,
            next_unit_ids=["unit-2"],
        ),
        source_evidence_refs=[_evidence()],
    )


def test_local_fragment_card_keeps_edge_and_source_evidence_immutable():
    card = _card()

    assert card.edge_metadata.touches_chunk_end is True
    assert card.source_evidence_refs[0].source_item_id == "source-1"
    assert card.source_evidence_refs[0].excerpt == "The local source evidence."

    with pytest.raises(ValidationError):
        card.summary = "rewritten"
    with pytest.raises(ValidationError):
        card.edge_metadata.touches_chunk_end = False
    with pytest.raises(ValidationError):
        card.source_evidence_refs[0].excerpt = "rewritten"
    with pytest.raises(ValidationError):
        card.source_evidence_refs += (_evidence(),)


def test_fragment_evidence_must_point_at_a_fragment_unit():
    with pytest.raises(ValidationError, match="fragment evidence"):
        LocalFragmentCard(
            fragment_id="fragment-1",
            summary="A fragment.",
            unit_ids=["unit-1"],
            edge_metadata=ChunkEdgeMetadata(),
            source_evidence_refs=[_evidence("unit-unknown")],
        )


def test_routes_are_limited_and_non_narrative_routes_receive_no_event_context():
    assert UnitRoute(local_unit_id="unit-1", route="narrative", fragment_ids=["fragment-1"])
    assert UnitRoute(local_unit_id="unit-2", route="reference_asset")
    assert UnitRoute(local_unit_id="unit-3", route="no_context")

    with pytest.raises(ValidationError):
        UnitRoute(local_unit_id="unit-2", route="reference_asset", fragment_ids=["fragment-1"])
    with pytest.raises(ValidationError):
        UnitRoute(local_unit_id="unit-3", route="unsupported")
    with pytest.raises(ValidationError):
        UnitRoute(local_unit_id="unit-4", route="narrative")


def test_story_groups_are_siblings_and_only_fragment_edges_are_ordered():
    story = Story(story_id="story-1", group_ids=["group-1", "group-2"])
    group = SiblingGroup(
        group_id="group-1",
        story_id=story.story_id,
        fragment_ids=["fragment-1", "fragment-2"],
    )
    edge = OrderedFragmentEdge(
        edge_id="edge-1",
        group_id=group.group_id,
        from_fragment_id="fragment-1",
        to_fragment_id="fragment-2",
        position=0,
    )

    assert story.group_ids == ("group-1", "group-2")
    assert group.fragment_ids == ("fragment-1", "fragment-2")
    assert edge.position == 0
    assert "order" not in Story.model_fields
    assert "position" not in SiblingGroup.model_fields

    with pytest.raises(ValidationError):
        OrderedFragmentEdge(
            group_id="group-1",
            from_fragment_id="fragment-1",
            to_fragment_id="fragment-1",
            position=0,
        )


def test_unresolved_reference_preserves_the_failed_link_and_one_repair_bound():
    unresolved = UnresolvedReference(
        reference_id="unresolved-1",
        reference_type="fragment",
        source_id="unit-1",
        target_id="fragment-missing",
        reason="The targeted fragment was absent after repair.",
        repair_attempts=1,
    )
    assert unresolved.target_id == "fragment-missing"

    with pytest.raises(ValidationError):
        unresolved.model_copy(update={"repair_attempts": 2})


def test_entity_digest_keeps_mechanical_description_segments_and_final_provenance():
    digest = EntityDigest(
        entity_id="entity-1",
        canonical_name="Remis",
        level="A",
        mechanical_local_description="A recurring archive protagonist.",
        partial_digests=(
            EntityDigestSegment(
                digest_segment_id="segment-1",
                summary="Appears in the opening batch.",
                evidence_unit_ids=("unit-1",),
                batch_indexes=(0,),
            ),
        ),
        final_digest="The final A-level entity digest.",
        digest_provenance="final",
    )

    assert digest.partial_digests[0].batch_indexes == (0,)
    assert digest.final_digest == "The final A-level entity digest."

    with pytest.raises(ValidationError):
        EntityDigest(
            entity_id="entity-c",
            canonical_name="A local candidate",
            level="C",
            final_digest="C must not receive a digest.",
            digest_provenance="final",
        )


@pytest.mark.parametrize(
    "operation",
    [
        TreeDraftOverrideOperation(
            operation="move_fragment",
            fragment_id="fragment-1",
            target_group_id="group-2",
            before_fragment_id="fragment-3",
        ),
        TreeDraftOverrideOperation(
            operation="reorder_fragment",
            group_id="group-2",
            fragment_id="fragment-1",
        ),
        TreeDraftOverrideOperation(
            operation="set_unit_route",
            local_unit_id="unit-1",
            route="reference_asset",
        ),
        TreeDraftOverrideOperation(
            operation="rename_group",
            group_id="group-2",
            new_name="Renamed group",
        ),
    ],
)
def test_tree_draft_operations_are_relationship_or_derived_changes(operation):
    assert operation.operation

    with pytest.raises(ValidationError):
        TreeDraftOverrideOperation(
            operation="move_fragment",
            fragment_id="fragment-1",
            target_group_id="group-2",
            source_evidence_refs=[_evidence()],
        )
    with pytest.raises(ValidationError):
        TreeDraftOverrideOperation(
            operation="rename_group",
            group_id="group-2",
            new_name="Renamed group",
            summary="source content is not a draft field",
        )


def test_read_tree_response_and_publication_validation_contracts_are_strict():
    tree = ReadTreeResponse(
        project_id="project-1",
        tree_id="tree-1",
        draft_id="draft-1",
        local_fragments=[_card()],
        unit_routes=[UnitRoute(local_unit_id="unit-1", route="narrative", fragment_ids=["fragment-1"])],
        stories=[Story(story_id="story-1", group_ids=["group-1"])],
        groups=[SiblingGroup(group_id="group-1", story_id="story-1", fragment_ids=["fragment-1"])],
        fragment_edges=[],
    )
    request = PrePublicationValidationRequest(
        project_id=tree.project_id,
        tree_id=tree.tree_id,
        draft_id=tree.draft_id,
    )
    result = PrePublicationValidationResult(
        project_id=request.project_id,
        tree_id=request.tree_id,
        draft_id=request.draft_id,
        valid=True,
        fragment_count=1,
        group_count=1,
        unit_route_count=1,
    )

    assert tree.local_fragments[0].fragment_id == "fragment-1"
    assert request.reject_unresolved is True
    assert result.valid is True

    large_route_response = ReadTreeResponse(
        project_id="project-1",
        tree_id="tree-large",
        unit_routes=[
            UnitRoute(local_unit_id=f"unit-{index}", route="narrative", fragment_ids=["fragment-1"])
            for index in range(201)
        ],
    )
    assert len(large_route_response.unit_routes) == 201

    with pytest.raises(ValidationError):
        ReadTreeResponse(project_id="project-1", tree_id="tree-1", unexpected=True)
    with pytest.raises(ValidationError):
        PrePublicationValidationResult(
            project_id="project-1",
            tree_id="tree-1",
            draft_id="draft-1",
            valid=True,
            errors=[
                PrePublicationValidationIssue(
                    code="missing_edge",
                    severity="error",
                    message="A fragment edge is missing.",
                )
            ],
        )
