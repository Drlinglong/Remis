import sqlite3

import pytest

from scripts.core.context_service import ContextService
from scripts.core.db_migrations import MAIN_DB_TARGET_VERSION, migrate_main_database
from scripts.core.repositories.context_repository import (
    ContextRepository,
    ImmutableContextReleaseError,
)
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextDeliveryMembership,
    ContextReleaseMetadata,
    ContextSourceItem,
    GeneratedSynthesis,
    HumanOverride,
)


def _repository(tmp_path):
    db_path = tmp_path / "context.sqlite"
    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO projects (
                project_id, name, game_id, source_path, source_language, status
            ) VALUES ('project-1', 'Context Mod', 'vic3', '/source', 'english', 'active')
            """
        )
    return ContextRepository(str(db_path)), db_path


def _metadata(parent_release_id=None, source_hash="snapshot-1"):
    return ContextReleaseMetadata(
        source_snapshot_hash=source_hash,
        analysis_scope={"files": ["common/characters.txt"]},
        schema_version="context-v1",
        prompt_version="prompt-v1",
        provider_id="local",
        model_id="model-under-test",
        analysis_config={"temperature": 0, "max_tokens": 1000},
        parent_release_id=parent_release_id,
    )


def _seed_context(repository, include_second=True):
    repository.create_source_item(
        ContextSourceItem(
            source_item_id="source-1",
            project_id="project-1",
            source_type="localization",
            source_ref="common/characters.txt:10",
            content="The Republic appoints a consul.",
            content_hash="hash-source-1",
        )
    )
    repository.create_contribution(
        ContextContribution(
            contribution_id="contribution-1",
            source_item_id="source-1",
            contribution_type="fact",
            subject_key="republic",
            payload={"office": "consul"},
            provenance="text_inferred",
        )
    )
    contribution_ids = ["contribution-1"]
    if include_second:
        repository.create_source_item(
            ContextSourceItem(
                source_item_id="source-2",
                project_id="project-1",
                source_type="script",
                source_ref="events/republic.txt:4",
                content="A consul is elected by script.",
                content_hash="hash-source-2",
            )
        )
        repository.create_contribution(
            ContextContribution(
                contribution_id="contribution-2",
                source_item_id="source-2",
                contribution_type="event",
                subject_key="republic",
                payload={"action": "elect"},
                provenance="script_derived",
            )
        )
        contribution_ids.append("contribution-2")
    repository.save_aggregate(
        ContextAggregate(
            aggregate_id="aggregate-republic",
            project_id="project-1",
            aggregate_type="entity",
            aggregate_key="republic",
            payload={"name": "Republic"},
            contribution_ids=contribution_ids,
        )
    )


def _publish(service, parent_release_id=None, source_hash="snapshot-1"):
    draft = service.start_draft("project-1", parent_release_id)
    service.save_override(
        draft.draft_id,
        HumanOverride(
            target_key="republic",
            value={"preferred_name": "共和国"},
            note="human review",
        ),
    )
    return service.publish_draft(
        draft.draft_id,
        _metadata(parent_release_id=parent_release_id, source_hash=source_hash),
        ["aggregate-republic"],
        [
            GeneratedSynthesis(
                synthesis_id=f"synthesis-{source_hash}",
                aggregate_id="aggregate-republic",
                context_key="republic",
                content={"summary": "A republic appoints a consul."},
            )
        ],
    )


def test_context_migration_creates_traceable_storage_and_provenance_checks(tmp_path):
    repository, db_path = _repository(tmp_path)
    _seed_context(repository)

    assert [item.provenance for item in repository.list_contributions("project-1")] == [
        "text_inferred",
        "script_derived",
    ]
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'context_%'"
            )
        }
        assert {
            "context_source_items",
            "context_contributions",
            "context_aggregates",
            "context_releases",
            "context_drafts",
            "context_release_syntheses",
            "context_release_delivery_memberships",
            "context_release_overrides",
        } <= tables
    assert repository.get_aggregate("aggregate-republic").contribution_ids == [
        "contribution-1",
        "contribution-2",
    ]


def test_relationship_contributions_and_project_aggregates_are_first_class(tmp_path):
    repository, _ = _repository(tmp_path)
    repository.create_source_item(
        ContextSourceItem(
            source_item_id="source-project",
            project_id="project-1",
            source_type="localization",
            source_ref="events/project.yml:project.summary",
            content="The Republic protects the Meridian Gate.",
            content_hash="hash-project",
        )
    )
    relationship = repository.create_contribution(
        ContextContribution(
            contribution_id="relationship-1",
            source_item_id="source-project",
            contribution_type="relationship",
            subject_key="republic",
            payload={"relation": "protects", "object": "meridian-gate"},
            provenance="text_inferred",
        )
    )
    project_aggregate = repository.save_aggregate(
        ContextAggregate(
            aggregate_id="aggregate-project",
            project_id="project-1",
            aggregate_type="project",
            aggregate_key="project:summary",
            payload={"title": "Context Mod"},
            contribution_ids=[relationship.contribution_id],
        )
    )

    assert project_aggregate.aggregate_type == "project"
    assert repository.get_aggregate("aggregate-project").contribution_ids == [
        "relationship-1"
    ]


def test_publish_creates_effective_context_and_full_traceability(tmp_path):
    repository, _ = _repository(tmp_path)
    _seed_context(repository)
    service = ContextService(repository)

    release = _publish(service)
    effective = service.effective_context(release.release_id)
    assert effective is not None
    assert effective.generated_synthesis == {
        "republic": {"summary": "A republic appoints a consul."}
    }
    assert effective.human_overrides == {"republic": {"preferred_name": "共和国"}}
    assert effective.effective_context["republic"] == {
        "summary": "A republic appoints a consul.",
        "preferred_name": "共和国",
    }

    traceability = service.traceability(release.release_id)
    assert traceability[0]["aggregate"]["aggregate_key"] == "republic"
    assert [
        item["contribution"]["provenance"]
        for item in traceability[0]["contributions"]
    ] == ["text_inferred", "script_derived"]
    assert traceability[0]["contributions"][0]["source_item"]["source_ref"] == (
        "common/characters.txt:10"
    )


def test_release_snapshots_delivery_membership_counts_without_expanding_traceability(tmp_path):
    repository, _ = _repository(tmp_path)
    _seed_context(repository, include_second=False)
    repository.save_aggregate(ContextAggregate(
        aggregate_id="aggregate-event",
        project_id="project-1",
        aggregate_type="event",
        aggregate_key="event:republic-chain",
        contribution_ids=["contribution-1"],
    ))
    service = ContextService(repository)
    draft = service.start_draft("project-1")
    release = service.publish_draft(
        draft.draft_id,
        _metadata(),
        ["aggregate-event"],
        [GeneratedSynthesis(
            synthesis_id="synthesis-event",
            aggregate_id="aggregate-event",
            context_key="event:republic-chain",
            content={"summary": "A republic event chain."},
        )],
        [ContextDeliveryMembership(
            aggregate_id="aggregate-event",
            source_item_id="source-1",
            role="primary_member",
            confidence=0.9,
        )],
    )

    traceability = service.traceability(release.release_id)
    assert traceability[0]["delivery_membership"] == {
        "count": 1,
        "role_counts": {"primary_member": 1},
    }
    memberships = service.delivery_memberships(release.release_id)
    assert memberships[0]["aggregate"]["aggregate_key"] == "event:republic-chain"
    assert memberships[0]["source_item"]["source_item_id"] == "source-1"


def test_published_release_and_children_are_immutable(tmp_path):
    repository, db_path = _repository(tmp_path)
    _seed_context(repository, include_second=False)
    release = _publish(ContextService(repository))

    with pytest.raises(ImmutableContextReleaseError):
        repository.update_release(release.release_id, prompt_version="changed")
    with pytest.raises(ImmutableContextReleaseError):
        repository.delete_release(release.release_id)
    with sqlite3.connect(db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE context_releases SET prompt_version = 'changed' WHERE release_id = ?",
                (release.release_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "DELETE FROM context_release_syntheses WHERE release_id = ?",
                (release.release_id,),
            )


def test_new_draft_publishes_child_release_without_mutating_parent(tmp_path):
    repository, _ = _repository(tmp_path)
    _seed_context(repository, include_second=False)
    service = ContextService(repository)
    first = _publish(service)

    second_draft = service.start_draft("project-1", first.release_id)
    inherited = repository.get_draft(second_draft.draft_id)
    assert inherited is not None
    assert inherited.overrides == [
        HumanOverride(
            target_key="republic",
            value={"preferred_name": "共和国"},
            note="human review",
        )
    ]
    service.save_override(
        second_draft.draft_id,
        HumanOverride(target_key="republic", value={"preferred_name": "共和国（修订）"}),
    )
    second = service.publish_draft(
        second_draft.draft_id,
        _metadata(parent_release_id=first.release_id, source_hash="snapshot-2"),
        ["aggregate-republic"],
        [
            GeneratedSynthesis(
                synthesis_id="synthesis-2",
                aggregate_id="aggregate-republic",
                context_key="republic",
                content={"summary": "A revised republic context."},
            )
        ],
    )

    assert second.metadata.parent_release_id == first.release_id
    assert service.effective_context(first.release_id).effective_context["republic"] == {
        "summary": "A republic appoints a consul.",
        "preferred_name": "共和国",
    }
    assert service.effective_context(second.release_id).effective_context["republic"] == {
        "summary": "A revised republic context.",
        "preferred_name": "共和国（修订）",
    }


def test_child_resynthesis_preserves_parent_overrides_without_new_edits(tmp_path):
    repository, _ = _repository(tmp_path)
    _seed_context(repository, include_second=False)
    service = ContextService(repository)
    first = _publish(service)
    child_draft = service.start_draft("project-1", first.release_id)

    child = service.publish_draft(
        child_draft.draft_id,
        _metadata(parent_release_id=first.release_id, source_hash="snapshot-resynthesized"),
        ["aggregate-republic"],
        [
            GeneratedSynthesis(
                synthesis_id="synthesis-resynthesized",
                aggregate_id="aggregate-republic",
                context_key="republic",
                content={"summary": "A resynthesized republic context."},
            )
        ],
    )

    assert service.effective_context(child.release_id).effective_context["republic"] == {
        "summary": "A resynthesized republic context.",
        "preferred_name": "共和国",
    }


def test_publish_rejects_parent_metadata_that_contradicts_draft_base(tmp_path):
    repository, _ = _repository(tmp_path)
    _seed_context(repository, include_second=False)
    service = ContextService(repository)
    first = _publish(service)
    child_draft = service.start_draft("project-1", first.release_id)

    with pytest.raises(ValueError, match="must match the draft base_release_id"):
        service.publish_draft(
            child_draft.draft_id,
            _metadata(parent_release_id="different-release"),
            ["aggregate-republic"],
            [
                GeneratedSynthesis(
                    synthesis_id="synthesis-invalid-lineage",
                    aggregate_id="aggregate-republic",
                    context_key="republic",
                )
            ],
        )
    assert repository.get_draft(child_draft.draft_id).status == "draft"


def test_rebuild_from_remaining_contributions_omits_removed_evidence_only_in_new_release(
    tmp_path,
):
    repository, _ = _repository(tmp_path)
    _seed_context(repository)
    service = ContextService(repository)
    first = _publish(service)

    repository.save_aggregate(
        ContextAggregate(
            aggregate_id="aggregate-republic",
            project_id="project-1",
            aggregate_type="entity",
            aggregate_key="republic",
            payload={"name": "Republic", "rebuild": 2},
            contribution_ids=["contribution-1"],
        )
    )
    second = service.publish_draft(
        service.start_draft("project-1", first.release_id).draft_id,
        _metadata(parent_release_id=first.release_id, source_hash="snapshot-remaining"),
        ["aggregate-republic"],
        [
            GeneratedSynthesis(
                synthesis_id="synthesis-remaining",
                aggregate_id="aggregate-republic",
                context_key="republic",
                content={"summary": "Rebuilt from remaining evidence."},
            )
        ],
    )

    old_trace = service.traceability(first.release_id)[0]["contributions"]
    new_trace = service.traceability(second.release_id)[0]["contributions"]
    assert [item["contribution"]["contribution_id"] for item in old_trace] == [
        "contribution-1",
        "contribution-2",
    ]
    assert [item["contribution"]["contribution_id"] for item in new_trace] == [
        "contribution-1"
    ]
    assert repository.get_source_item("source-2") is not None


def test_release_metadata_rejects_credentials(tmp_path):
    _repository(tmp_path)
    with pytest.raises(ValueError, match="credentials"):
        ContextReleaseMetadata(
            source_snapshot_hash="snapshot",
            schema_version="context-v1",
            prompt_version="prompt-v1",
            provider_id="local",
            model_id="model",
            analysis_config={"api_key": "never-store"},
        )
