from __future__ import annotations

import sqlite3

import pytest

from scripts.core.context_service import ContextService
from scripts.core.db_migrations import MAIN_DB_TARGET_VERSION, migrate_main_database
from scripts.core.repositories.context_override_repository import (
    ContextKeyNotFoundError,
    ContextDraftClosedError,
    ContextOwnershipError,
    ContextOverrideRepository,
)
from scripts.core.repositories.context_repository import ContextRepository
from scripts.core.services.context_override_service import ContextOverrideService
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
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


def _seed_context(repository: ContextRepository) -> None:
    for source_id, reference, content in (
        ("source-1", "common/characters.txt:10", "The Republic appoints a consul."),
        ("source-2", "events/republic.txt:4", "A consul is elected by script."),
    ):
        repository.create_source_item(
            ContextSourceItem(
                source_item_id=source_id,
                project_id="project-1",
                source_type="localization",
                source_ref=reference,
                content=content,
                content_hash=f"hash-{source_id}",
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
    repository.save_aggregate(
        ContextAggregate(
            aggregate_id="aggregate-republic",
            project_id="project-1",
            aggregate_type="entity",
            aggregate_key="republic",
            payload={"name": "Republic", "snapshot": "A"},
            contribution_ids=["contribution-1", "contribution-2"],
        )
    )


def _base_release(repository: ContextRepository):
    service = ContextService(repository)
    draft = service.start_draft("project-1")
    service.save_override(
        draft.draft_id,
        HumanOverride(
            target_key="republic",
            value={"preferred_name": "共和国"},
            note="inherited review",
        ),
    )
    return service.publish_draft(
        draft.draft_id,
        ContextReleaseMetadata(
            source_snapshot_hash="source-snapshot-A",
            analysis_scope={"mode": "narrative_context"},
            schema_version="context-v1",
            prompt_version="prompt-v1",
            provider_id="local",
            model_id="model-under-test",
        ),
        ["aggregate-republic"],
        [
            GeneratedSynthesis(
                synthesis_id="synthesis-A",
                aggregate_id="aggregate-republic",
                context_key="republic",
                content={"summary": "The Republic appoints and elects a consul."},
            )
        ],
    )


def _release_rows(db_path, release_id):
    with sqlite3.connect(db_path) as connection:
        aggregate = connection.execute(
            """
            SELECT aggregate_id, aggregate_type, aggregate_key, payload_json,
                   contribution_ids_json
            FROM context_release_aggregates WHERE release_id = ?
            """,
            (release_id,),
        ).fetchall()
        syntheses = connection.execute(
            """
            SELECT aggregate_id, context_key, content_json
            FROM context_release_syntheses WHERE release_id = ?
            """,
            (release_id,),
        ).fetchall()
    return aggregate, syntheses


def test_override_publish_copies_parent_snapshots_after_current_aggregate_drift(tmp_path):
    repository, db_path = _repository(tmp_path)
    _seed_context(repository)
    parent = _base_release(repository)
    parent_rows = _release_rows(db_path, parent.release_id)
    override_service = ContextOverrideService(ContextOverrideRepository(str(db_path)))

    draft = override_service.start_draft("project-1", parent.release_id)
    assert draft.overrides == [
        HumanOverride(
            target_key="republic",
            value={"preferred_name": "共和国"},
            note="inherited review",
        )
    ]

    repository.save_aggregate(
        ContextAggregate(
            aggregate_id="aggregate-republic",
            project_id="project-1",
            aggregate_type="entity",
            aggregate_key="republic",
            payload={"name": "Republic", "snapshot": "B", "replacement": True},
            contribution_ids=["contribution-1"],
        )
    )
    updated_draft = override_service.save_override(
        "project-1",
        draft.draft_id,
        "republic",
        {"preferred_name": "共和国（已确认）", "entity_type": "state"},
        "human correction",
    )
    child = override_service.publish_draft("project-1", draft.draft_id)

    assert child.metadata.parent_release_id == parent.release_id
    assert child.metadata.source_snapshot_hash == parent.metadata.source_snapshot_hash
    assert child.metadata.created_at != parent.metadata.created_at
    assert updated_draft.overrides[0].value["entity_type"] == "state"
    assert _release_rows(db_path, parent.release_id) == parent_rows
    assert _release_rows(db_path, child.release_id)[0] == parent_rows[0]
    assert _release_rows(db_path, child.release_id)[1][0][2] == parent_rows[1][0][2]

    parent_effective = repository.get_effective_context(parent.release_id)
    child_effective = repository.get_effective_context(child.release_id)
    assert parent_effective.effective_context["republic"] == {
        "summary": "The Republic appoints and elects a consul.",
        "preferred_name": "共和国",
    }
    assert child_effective.effective_context["republic"] == {
        "summary": "The Republic appoints and elects a consul.",
        "preferred_name": "共和国（已确认）",
        "entity_type": "state",
    }
    assert repository.get_release_traceability(child.release_id)[0]["aggregate"]["payload"] == {
        "name": "Republic",
        "snapshot": "A",
    }
    with pytest.raises(ContextDraftClosedError):
        override_service.publish_draft("project-1", draft.draft_id)


def test_override_repository_rejects_unknown_key_and_wrong_project(tmp_path):
    repository, db_path = _repository(tmp_path)
    _seed_context(repository)
    parent = _base_release(repository)
    service = ContextOverrideService(ContextOverrideRepository(str(db_path)))
    draft = service.start_draft("project-1", parent.release_id)

    with pytest.raises(ContextKeyNotFoundError, match="parent release"):
        service.save_override(
            "project-1", draft.draft_id, "missing", {"summary": "no"}, None
        )
    with pytest.raises(ContextOwnershipError, match="does not belong"):
        service.get_draft("project-2", draft.draft_id)
