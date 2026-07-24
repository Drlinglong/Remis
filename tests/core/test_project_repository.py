
import pytest
import pytest_asyncio
import os
from datetime import datetime
from sqlmodel import select
from scripts.core.repositories.project_repository import ProjectRepository
from scripts.core.repositories.project_watch_repository import ProjectWatchRepository
from scripts.core.glossary_manager import GlossaryManager
from scripts.core.db_models import (
    ActivityLog,
    Glossary,
    Project,
    ProjectFile,
    ProjectGlossaryBinding,
    ProjectHistory,
    ProjectWatch,
    ProjectWatchFileSnapshot,
)
from scripts.core.db_manager import DatabaseConnectionManager, db_manager

@pytest_asyncio.fixture
async def repo(tmp_path):
    test_db_path = str(tmp_path / "projects.db")

    from scripts.core.db_manager import db_manager
    original_path = db_manager.db_path
    engine = None

    try:
        # Reset singleton state before switching the database path.
        if hasattr(db_manager, '_async_engine'):
            await db_manager._async_engine.dispose()
            del db_manager._async_engine
        if hasattr(db_manager, '_sync_engine'):
            db_manager._sync_engine.dispose()
            del db_manager._sync_engine

        db_manager.db_path = test_db_path

        from sqlmodel import SQLModel
        engine = db_manager.get_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        yield ProjectRepository(test_db_path)
    finally:
        if engine is not None:
            await engine.dispose()
        if hasattr(db_manager, '_async_engine'):
            await db_manager._async_engine.dispose()
            del db_manager._async_engine
        if hasattr(db_manager, '_sync_engine'):
            db_manager._sync_engine.dispose()
            del db_manager._sync_engine
        db_manager.db_path = original_path

@pytest.mark.asyncio
async def test_create_and_get_project(repo):
    # Arrange
    project_id = "test_proj_1"
    new_project = Project(
        project_id=project_id,
        name="Test Project 1",
        game_id="stellaris",
        source_path="/tmp/source",
        source_language="english",
        status="active",
        created_at=datetime.now().isoformat(),
        last_modified=datetime.now().isoformat()
    )
    
    # Act
    created = await repo.create_project(new_project)
    fetched = await repo.get_project(project_id)
    
    # Assert
    assert created.project_id == project_id
    assert fetched is not None
    assert fetched.project_id == project_id
    assert fetched.name == "Test Project 1"
    assert fetched.source_language == "english"


@pytest.mark.asyncio
async def test_archive_pauses_enabled_watches_and_restore_preserves_manual_choices(repo):
    project_id = "archive-watch-project"
    await repo.create_project(
        Project(
            project_id=project_id,
            name="Long-term Shelf Project",
            game_id="victoria3",
            source_path="/tmp/archive-watch-project",
            source_language="english",
            status="active",
        )
    )
    watch_repo = ProjectWatchRepository(repo.db_path)
    for watch_id, enabled in [
        ("enabled-watch-1", True),
        ("enabled-watch-2", True),
        ("already-disabled-watch", False),
    ]:
        await watch_repo.create_watch(
            {
                "watch_id": watch_id,
                "name": watch_id,
                "path": f"/tmp/{watch_id}",
                "project_id": project_id,
                "enabled": enabled,
                "scan_interval_minutes": 60,
            }
        )
    await watch_repo.create_watch(
        {
            "watch_id": "unrelated-watch",
            "name": "unrelated-watch",
            "path": "/tmp/unrelated-watch",
            "enabled": True,
            "scan_interval_minutes": 60,
        }
    )

    archived = await repo.update_project_lifecycle_status(project_id, "archived")

    assert archived["paused_watch_count"] == 2
    assert (await watch_repo.get_watch("enabled-watch-1")).enabled is False
    assert (await watch_repo.get_watch("enabled-watch-1")).paused_by_project_archive is True
    assert (await watch_repo.get_watch("enabled-watch-2")).paused_by_project_archive is True
    assert (await watch_repo.get_watch("already-disabled-watch")).paused_by_project_archive is False
    assert (await watch_repo.get_watch("unrelated-watch")).enabled is True

    # A manual choice made while archived takes precedence over automatic restore.
    await watch_repo.update_watch("enabled-watch-2", {"enabled": False})
    await repo.update_project_lifecycle_status(project_id, "deleted")
    restored = await repo.update_project_lifecycle_status(project_id, "active")

    assert restored["restored_watch_count"] == 1
    assert (await watch_repo.get_watch("enabled-watch-1")).enabled is True
    assert (await watch_repo.get_watch("enabled-watch-1")).paused_by_project_archive is False
    assert (await watch_repo.get_watch("enabled-watch-2")).enabled is False
    assert (await watch_repo.get_watch("already-disabled-watch")).enabled is False

@pytest.mark.asyncio
async def test_create_project_does_not_mutate_input_model(repo):
    project_id = "test_proj_no_mutation"
    source_path = os.path.join(os.getcwd(), "source_mod", "mutation_source")
    target_path = os.path.join(os.getcwd(), "my_translation", "mutation_target")
    new_project = Project(
        project_id=project_id,
        name="No Mutation Test",
        game_id="stellaris",
        source_path=source_path,
        target_path=target_path,
        source_language="english",
        status="active",
    )

    created = await repo.create_project(new_project)

    assert created is not new_project
    assert new_project.source_path == source_path
    assert new_project.target_path == target_path


@pytest.mark.asyncio
async def test_delete_project_removes_foreign_key_dependents(repo):
    project_id = "project-with-dependents"
    await repo.create_project(Project(
        project_id=project_id,
        name="Delete Me",
        game_id="eu5",
        source_path="/tmp/delete-me",
        source_language="english",
    ))

    async for session in db_manager.get_async_session():
        glossary = Glossary(game_id="eu5", name="Bound Glossary")
        session.add(glossary)
        await session.flush()
        session.add_all([
            ProjectFile(file_id="delete-file", project_id=project_id, file_path="a.yml"),
            ProjectHistory(
                history_id="delete-history",
                project_id=project_id,
                timestamp=datetime.now().isoformat(),
                action_type="import",
            ),
            ActivityLog(
                log_id="delete-activity",
                project_id=project_id,
                type="import",
                description="Imported",
                timestamp=datetime.now().isoformat(),
            ),
            ProjectGlossaryBinding(project_id=project_id, glossary_id=glossary.glossary_id),
            ProjectWatch(watch_id="delete-watch", name="Delete Watch", path="/tmp", project_id=project_id),
        ])
        session.add(ProjectWatchFileSnapshot(
            snapshot_id="delete-snapshot",
            watch_id="delete-watch",
            relative_path="a.yml",
            sha256="hash",
            size=1,
            mtime_ns=1,
            last_seen_at=datetime.now().isoformat(),
        ))
        await session.commit()
        break

    await repo.delete_project(project_id)

    async for session in db_manager.get_async_session():
        for model in (
            Project,
            ProjectFile,
            ProjectHistory,
            ActivityLog,
            ProjectGlossaryBinding,
            ProjectWatch,
            ProjectWatchFileSnapshot,
        ):
            result = await session.execute(select(model))
            assert result.scalars().all() == []
        break


@pytest.mark.asyncio
async def test_delete_glossary_removes_project_binding(repo):
    project_id = "project-with-bound-glossary"
    await repo.create_project(Project(
        project_id=project_id,
        name="Keep Project",
        game_id="eu5",
        source_path="/tmp/keep-project",
        source_language="english",
    ))

    async for session in db_manager.get_async_session():
        glossary = Glossary(game_id="eu5", name="Delete Bound Glossary")
        session.add(glossary)
        await session.flush()
        glossary_id = glossary.glossary_id
        session.add(ProjectGlossaryBinding(project_id=project_id, glossary_id=glossary_id))
        await session.commit()
        break

    assert await GlossaryManager().delete_glossary(glossary_id) is True

    async for session in db_manager.get_async_session():
        binding_result = await session.execute(select(ProjectGlossaryBinding))
        glossary_result = await session.execute(select(Glossary))
        project_result = await session.execute(select(Project))
        assert binding_result.scalars().all() == []
        assert glossary_result.scalars().all() == []
        assert [project.project_id for project in project_result.scalars().all()] == [project_id]
        break

@pytest.mark.asyncio
async def test_batch_upsert_files_does_not_mutate_input_payload(repo):
    project_id = "test_proj_file_payload_no_mutation"
    await repo.create_project(Project(
        project_id=project_id,
        name="File Payload No Mutation",
        game_id="stellaris",
        source_path="/tmp/source_payload",
        source_language="english"
    ))

    files_data = [{
        "file_id": "payload_f1",
        "project_id": project_id,
        "file_path": r"C:\tmp\source_payload\f1.yml",
        "status": "todo",
        "original_key_count": 10,
        "line_count": 100,
        "file_type": "source"
    }]
    original_path = files_data[0]["file_path"]

    await repo.batch_upsert_files(files_data)

    assert files_data[0]["file_path"] == original_path

@pytest.mark.asyncio
async def test_repository_does_not_commit_caller_owned_session(repo):
    from scripts.core.db_manager import db_manager

    project_id = "test_proj_external_session"
    async for session in db_manager.get_async_session():
        await repo.create_project(Project(
            project_id=project_id,
            name="External Session Test",
            game_id="stellaris",
            source_path="/tmp/external_session",
            source_language="english",
            status="active",
        ), session=session)
        await session.rollback()
        break

    fetched = await repo.get_project(project_id)
    assert fetched is None

@pytest.mark.asyncio
async def test_update_project_metadata(repo):
    # Arrange
    project_id = "test_proj_meta"
    new_project = Project(
        project_id=project_id,
        name="Meta Test",
        game_id="stellaris",
        source_path="/tmp/source_meta",
        source_language="english",
        status="active"
    )
    await repo.create_project(new_project)
    
    # Act
    await repo.update_project_metadata(project_id, "hoi4", "german")
    fetched = await repo.get_project(project_id)
    
    # Assert
    assert fetched.game_id == "hoi4"
    assert fetched.source_language == "german"

@pytest.mark.asyncio
async def test_batch_upsert_files(repo):
    # Arrange
    project_id = "test_proj_files"
    await repo.create_project(Project(
        project_id=project_id,
        name="Files Test",
        game_id="stellaris",
        source_path="/tmp/source_files",
        source_language="english"
    ))
    
    files_data = [
        {
            "file_id": "f1",
            "project_id": project_id,
            "file_path": "/tmp/source_files/f1.yml",
            "status": "todo",
            "original_key_count": 10,
            "line_count": 100,
            "file_type": "source"
        },
        {
            "file_id": "f2",
            "project_id": project_id,
            "file_path": "/tmp/source_files/f2.yml",
            "status": "done",
            "original_key_count": 20,
            "line_count": 200,
            "file_type": "translation"
        }
    ]
    
    # Act
    await repo.batch_upsert_files(files_data)
    files = await repo.get_project_files(project_id)
    
    # Assert
    assert len(files) == 2
    f1 = next(f for f in files if f.file_id == "f1")
    assert f1.status == "todo"
    assert f1.original_key_count == 10

@pytest.mark.asyncio
async def test_legacy_translated_status_is_normalized_on_write(repo):
    project_id = "test_proj_legacy_status"
    await repo.create_project(Project(
        project_id=project_id,
        name="Legacy Status Test",
        game_id="eu4",
        source_path="/tmp/source_legacy_status",
        source_language="english"
    ))

    await repo.batch_upsert_files([
        {
            "file_id": "legacy-file",
            "project_id": project_id,
            "file_path": "/tmp/source_legacy_status/file.yml",
            "status": "translated",
            "original_key_count": 7,
            "line_count": 20,
            "file_type": "source"
        }
    ])

    files = await repo.get_project_files(project_id)
    assert files[0].status == "done"

@pytest.mark.asyncio
async def test_legacy_translated_status_counts_as_done_in_dashboard(repo):
    project_id = "test_proj_legacy_dashboard"
    await repo.create_project(Project(
        project_id=project_id,
        name="Legacy Dashboard Test",
        game_id="eu4",
        source_path="/tmp/source_legacy_dashboard",
        source_language="english"
    ))

    files = [
        {"file_id": "legacy-done", "project_id": project_id, "file_path": "/tmp/source_legacy_dashboard/done.yml", "status": "done", "original_key_count": 5, "line_count": 10, "file_type": "source"},
        {"file_id": "legacy-translated", "project_id": project_id, "file_path": "/tmp/source_legacy_dashboard/translated.yml", "status": "translated", "original_key_count": 3, "line_count": 10, "file_type": "source"}
    ]
    await repo.batch_upsert_files(files)
    from sqlalchemy import text
    async with repo._use_session() as session:
        await session.execute(
            text("UPDATE project_files SET status = 'translated' WHERE file_id = 'legacy-translated'")
        )
        await session.commit()

    stats = await repo.get_dashboard_stats()

    assert stats["translated_keys"] == 8
    assert stats["translated_files"] == 2

@pytest.mark.asyncio
async def test_get_dashboard_stats(repo):
    # Arrange
    # Project 1: Active, 10 keys todo
    p1 = Project(project_id="p1", name="P1", game_id="stellaris", source_path="/p1", source_language="en", status="active")
    await repo.create_project(p1)
    
    # Project 2: Archived, 0 keys
    p2 = Project(project_id="p2", name="P2", game_id="hoi4", source_path="/p2", source_language="en", status="archived")
    await repo.create_project(p2)
    
    files = [
        {"file_id": "f1", "project_id": "p1", "file_path": "/p1/f1", "status": "todo", "original_key_count": 10, "line_count": 10, "file_type": "source"},
        {"file_id": "f2", "project_id": "p1", "file_path": "/p1/f2", "status": "done", "original_key_count": 5, "line_count": 5, "file_type": "source"}
    ]
    await repo.batch_upsert_files(files)
    
    # Act
    stats = await repo.get_dashboard_stats()
    
    # Assert
    # total_projects = 2
    assert stats["total_projects"] == 2
    # active_projects = 1
    assert stats["active_projects"] == 1
    # total_files = 2
    assert stats["total_files"] == 2
    # total_keys = 15 (10 + 5)
    assert stats["total_keys"] == 15
    # translated_keys = 5 (from status='done')
    assert stats["translated_keys"] == 5
    # completion_rate = 5/15 = 33.3%
    assert 33.0 < stats["completion_rate"] < 34.0
    
    # Game distribution
    dist = stats["game_distribution"]
    msg = f"Distribution: {dist}"
    # Expect: [{'name': 'stellaris', 'value': 1}, {'name': 'hoi4', 'value': 1}] (order may vary)
    assert len(dist) == 2, msg
    assert any(d['name'] == 'stellaris' and d['value'] == 1 for d in dist), msg
