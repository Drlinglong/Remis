import sqlite3

import pytest

from scripts.core.context_tree_v2_migration import migrate_context_tree_v2_storage
from scripts.core.repositories.context_tree_v2_repository import ContextTreeV2Repository
from scripts.schemas.context_tree_v2 import (
    ChunkEdgeMetadata,
    EntityAliasDescription,
    EntityDigest,
    EntityEvidenceReference,
    LocalFragmentCard,
    ReadTreeResponse,
    SiblingGroup,
    SourceEvidenceReference,
    Story,
    TreeDraftOverrideOperation,
    UnitRoute,
)


@pytest.fixture
def repository(tmp_path):
    db_path = tmp_path / "context-tree-v2-repository.sqlite"
    migrate_context_tree_v2_storage(str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE projects (project_id TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO projects VALUES ('project-1')")
    return ContextTreeV2Repository(str(db_path))


def _tree() -> ReadTreeResponse:
    evidence = SourceEvidenceReference(
        source_item_id="source-1",
        source_ref="events.yml:12",
        local_unit_id="unit-1",
        item_key="event.one.desc",
        batch_source="batch-01",
        full_source_text="The complete source item remains outside the digest request budget.",
    )
    entity_evidence = EntityEvidenceReference(
        evidence_id="evidence-1",
        entity_id="entity-remis",
        source_item_id="source-1",
        source_ref="events.yml:12",
        local_unit_id="unit-1",
        batch_source="batch-01",
        batch_id="batch-01",
        included_in_digest=True,
        digest_segment_id="digest-segment-1",
        digest_provenance="final",
    )
    return ReadTreeResponse(
        project_id="project-1",
        tree_id="tree-1",
        source_snapshot_hash="snapshot-1",
        schema_version="context-tree-v2",
        prompt_version="prompt-v2",
        project_summary="A compact project preview for ordinary and translation views.",
        local_fragments=(
            LocalFragmentCard(
                fragment_id="fragment-1",
                summary="The first local event.",
                unit_ids=("unit-1",),
                edge_metadata=ChunkEdgeMetadata(chunk_id="chunk-1"),
                source_evidence_refs=(evidence,),
            ),
        ),
        unit_routes=(UnitRoute(local_unit_id="unit-1", route="narrative", fragment_ids=("fragment-1",)),),
        stories=(Story(story_id="story-1", group_ids=("group-1", "group-2")),),
        groups=(
            SiblingGroup(group_id="group-1", story_id="story-1", fragment_ids=("fragment-1",)),
            SiblingGroup(group_id="group-2", story_id="story-1"),
        ),
        entity_evidence=(entity_evidence,),
        entity_digests=(
            EntityDigest(
                entity_id="entity-remis",
                canonical_name="Remis",
                level="A",
                summary="The archive's recurring protagonist.",
                alias_descriptions=(
                    EntityAliasDescription(alias="the Red Archivist", description="An archive alias."),
                ),
                evidence_ids=("evidence-1",),
                digest_segment_ids=("digest-segment-1",),
                source_batch_ids=("batch-01",),
                digest_provenance="final",
            ),
        ),
    )


def test_repository_round_trips_full_entity_evidence_without_digest_budget_crop(repository):
    stored = repository.save_tree(_tree())

    assert len(stored.entity_evidence) == 1
    assert stored.entity_evidence[0].digest_segment_id == "digest-segment-1"
    assert stored.entity_evidence[0].batch_source == "batch-01"
    assert stored.entity_digests[0].alias_descriptions[0].description == "An archive alias."
    assert stored.project_summary.startswith("A compact project")
    assert stored.local_fragments[0].source_evidence_refs[0].full_source_text.startswith("The complete")


def test_draft_move_changes_relationship_projection_but_not_source_evidence(repository):
    repository.save_tree(_tree())
    draft = repository.create_draft("project-1", "tree-1")
    repository.save_draft_operation(
        "project-1",
        draft.draft_id,
        TreeDraftOverrideOperation(
            operation="move_fragment",
            fragment_id="fragment-1",
            target_group_id="group-2",
        ),
    )

    projected = repository.get_tree("project-1", "tree-1", draft.draft_id)
    base = repository.get_tree("project-1", "tree-1")
    assert projected.groups[0].fragment_ids == ()
    assert projected.groups[1].fragment_ids == ("fragment-1",)
    assert base.groups[0].fragment_ids == ("fragment-1",)
    assert projected.local_fragments[0].source_evidence_refs[0].source_item_id == "source-1"


def test_source_rows_are_immutable(repository):
    repository.save_tree(_tree())
    with sqlite3.connect(repository.db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE context_tree_v2_fragments SET summary = 'rewritten' WHERE tree_id = 'tree-1'"
            )


def test_latest_and_release_read_aliases(repository):
    repository.save_tree(_tree())
    draft = repository.create_draft("project-1", "tree-1")
    release = repository.publish_draft("project-1", draft.draft_id, idempotency_key="release-1")

    assert repository.get_latest_tree("project-1").tree_id == "tree-1"
    assert repository.get_release_tree("project-1", release["release_id"]).tree_id == "tree-1"
    assert repository.publish_draft("project-1", draft.draft_id, idempotency_key="release-1")["release_id"] == release["release_id"]
