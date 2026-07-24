from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.future import select
from sqlmodel import SQLModel

from scripts.core.db_manager import db_manager
from scripts.core.db_models import Glossary, GlossaryEntry, Project, ProjectGlossaryBinding
from scripts.core.glossary_manager import GlossaryManager


@pytest_asyncio.fixture
async def glossary_database(tmp_path):
    original_path = db_manager.db_path
    engine = None

    try:
        if hasattr(db_manager, "_async_engine"):
            await db_manager._async_engine.dispose()
            del db_manager._async_engine
        if hasattr(db_manager, "_sync_engine"):
            db_manager._sync_engine.dispose()
            del db_manager._sync_engine

        db_manager.db_path = str(tmp_path / "glossary-overview.sqlite")
        engine = db_manager.get_async_engine()
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

        yield
    finally:
        if engine is not None:
            await engine.dispose()
        if hasattr(db_manager, "_async_engine"):
            await db_manager._async_engine.dispose()
            del db_manager._async_engine
        if hasattr(db_manager, "_sync_engine"):
            db_manager._sync_engine.dispose()
            del db_manager._sync_engine
        db_manager.db_path = original_path


@pytest.mark.asyncio
async def test_glossary_overview_aggregates_inventory_and_project_bindings(glossary_database):
    updated_at = datetime.now().isoformat()

    async for session in db_manager.get_async_session():
        main_glossary = Glossary(game_id="vic3", name="Victoria 3 Main", is_main=True)
        project_glossary = Glossary(
            game_id="stellaris",
            name="Project Terms",
            raw_metadata={
                "kind": "project_neologism_glossary",
                "owner_project_id": "project-1",
            },
        )
        empty_glossary = Glossary(game_id="vic3", name="Scratchpad")
        session.add_all([main_glossary, project_glossary, empty_glossary])
        await session.flush()

        session.add(Project(
            project_id="project-1",
            name="Community Translation",
            game_id="stellaris",
            source_path="/tmp/project-1",
            source_language="english",
        ))
        session.add_all([
            GlossaryEntry(
                entry_id="term-1",
                glossary_id=main_glossary.glossary_id,
                translations={"en": "Prestige", "zh-CN": "威望"},
            ),
            GlossaryEntry(
                entry_id="term-2",
                glossary_id=main_glossary.glossary_id,
                translations={"en": "Authority", "zh-CN": "权威"},
            ),
            ProjectGlossaryBinding(
                project_id="project-1",
                glossary_id=project_glossary.glossary_id,
                created_at=updated_at,
                updated_at=updated_at,
            ),
        ])
        await session.commit()
        break

    overview = await GlossaryManager().get_glossary_overview()

    assert overview["summary"] == {
        "game_count": 2,
        "glossary_count": 3,
        "term_count": 2,
        "main_glossary_count": 1,
        "project_glossary_count": 1,
        "bound_project_count": 1,
    }

    inventory = {item["name"]: item for item in overview["glossaries"]}
    assert inventory["Victoria 3 Main"]["kind"] == "main"
    assert inventory["Victoria 3 Main"]["entry_count"] == 2
    assert inventory["Scratchpad"]["entry_count"] == 0
    assert inventory["Project Terms"]["kind"] == "project"
    assert inventory["Project Terms"]["updated_at"] is None
    assert inventory["Project Terms"]["bound_projects"] == [{
        "project_id": "project-1",
        "name": "Community Translation",
        "game_id": "stellaris",
    }]


@pytest.mark.asyncio
async def test_duplicate_glossary_preserves_entries_and_records_lineage(glossary_database):
    async for session in db_manager.get_async_session():
        source = Glossary(
            game_id="stellaris",
            name="Project Terms",
            description="Terms mined from a mod",
            version="2",
            is_main=True,
            sources=["localization.yml"],
            raw_metadata={
                "kind": "project_neologism_glossary",
                "owner_project_id": "project-1",
                "custom": "kept",
            },
        )
        session.add(source)
        await session.flush()
        source_id = source.glossary_id
        session.add(GlossaryEntry(
            entry_id="source-entry",
            glossary_id=source_id,
            translations={"en": "Admiral", "zh-CN": "海军上将"},
            abbreviations={"en": "Adm."},
            variants={"en": ["Fleet Admiral"]},
            raw_metadata={"remarks": "naval rank", "custom": {"score": 1}},
        ))
        await session.commit()
        break

    result = await GlossaryManager().duplicate_glossary(source_id, "Project Terms - Review Copy")

    assert result["name"] == "Project Terms - Review Copy"
    assert result["entry_count"] == 1
    assert result["copied_from"] == {
        "glossary_id": source_id,
        "game_id": "stellaris",
        "name": "Project Terms",
    }

    async for session in db_manager.get_async_session():
        copy_result = await session.execute(
            select(Glossary).where(Glossary.glossary_id == result["glossary_id"])
        )
        copied_glossary = copy_result.scalar_one()
        entry_result = await session.execute(
            select(GlossaryEntry).where(GlossaryEntry.glossary_id == result["glossary_id"])
        )
        copied_entry = entry_result.scalar_one()
        break

    assert copied_glossary.game_id == "stellaris"
    assert copied_glossary.description == "Terms mined from a mod"
    assert copied_glossary.version == "2"
    assert copied_glossary.is_main is False
    assert copied_glossary.sources == ["localization.yml"]
    assert copied_glossary.raw_metadata["custom"] == "kept"
    assert "owner_project_id" not in copied_glossary.raw_metadata
    assert "kind" not in copied_glossary.raw_metadata
    assert copied_entry.entry_id != "source-entry"
    assert copied_entry.translations == {"en": "Admiral", "zh-CN": "海军上将"}
    assert copied_entry.abbreviations == {"en": "Adm."}
    assert copied_entry.variants == {"en": ["Fleet Admiral"]}
    assert copied_entry.raw_metadata == {
        "remarks": "naval rank",
        "custom": {"score": 1},
    }


@pytest.mark.asyncio
async def test_duplicate_glossary_rejects_same_game_name_collision(glossary_database):
    async for session in db_manager.get_async_session():
        source = Glossary(game_id="vic3", name="Main Terms")
        session.add_all([source, Glossary(game_id="vic3", name="Existing Copy")])
        await session.flush()
        source_id = source.glossary_id
        await session.commit()
        break

    with pytest.raises(ValueError, match="already exists"):
        await GlossaryManager().duplicate_glossary(source_id, "existing copy")


@pytest.mark.asyncio
async def test_update_glossary_metadata_preserves_system_owned_fields(glossary_database):
    async for session in db_manager.get_async_session():
        glossary = Glossary(
            game_id="vic3",
            name="Auto-mined Terms",
            description="Auto-mined project glossary for Remis Demo",
            is_main=False,
            sources=["localization.yml"],
            raw_metadata={
                "kind": "project_neologism_glossary",
                "owner_project_id": "project-1",
            },
        )
        session.add(glossary)
        await session.flush()
        glossary_id = glossary.glossary_id
        await session.commit()
        break

    result = await GlossaryManager().update_glossary_metadata(
        glossary_id,
        name="Remis Demo Terms",
        description="Reviewed terminology for the Victoria 3 demo mod.",
    )

    assert result["name"] == "Remis Demo Terms"
    assert result["description"] == "Reviewed terminology for the Victoria 3 demo mod."
    assert result["kind"] == "project"
    assert result["updated_at"]

    async for session in db_manager.get_async_session():
        updated = (await session.execute(
            select(Glossary).where(Glossary.glossary_id == glossary_id)
        )).scalar_one()
        break

    assert updated.game_id == "vic3"
    assert updated.is_main is False
    assert updated.sources == ["localization.yml"]
    assert updated.raw_metadata["kind"] == "project_neologism_glossary"
    assert updated.raw_metadata["owner_project_id"] == "project-1"
    assert updated.raw_metadata["updated_at"] == result["updated_at"]


@pytest.mark.asyncio
async def test_update_glossary_metadata_manages_many_to_many_project_bindings(glossary_database):
    async for session in db_manager.get_async_session():
        glossary = Glossary(game_id="vic3", name="Shared Mod Terms")
        projects = [
            Project(
                project_id="project-1",
                name="First Mod",
                game_id="vic3",
                source_path="/tmp/project-1",
                source_language="english",
            ),
            Project(
                project_id="project-2",
                name="Second Mod",
                game_id="vic3",
                source_path="/tmp/project-2",
                source_language="english",
            ),
        ]
        session.add(glossary)
        session.add_all(projects)
        await session.flush()
        glossary_id = glossary.glossary_id
        await session.commit()
        break

    manager = GlossaryManager()
    result = await manager.update_glossary_metadata(
        glossary_id,
        name="Shared Mod Terms",
        description="Used by two mods.",
        kind="project",
        project_ids=["project-1", "project-2"],
    )

    assert result["kind"] == "project"
    assert [item["project_id"] for item in result["bound_projects"]] == [
        "project-1",
        "project-2",
    ]

    async for session in db_manager.get_async_session():
        bindings = (await session.execute(
            select(ProjectGlossaryBinding).where(
                ProjectGlossaryBinding.glossary_id == glossary_id
            )
        )).scalars().all()
        updated = (await session.execute(
            select(Glossary).where(Glossary.glossary_id == glossary_id)
        )).scalar_one()
        break

    assert {binding.project_id for binding in bindings} == {"project-1", "project-2"}
    assert updated.is_main is False
    assert updated.raw_metadata["kind"] == "project_glossary"
    assert updated.raw_metadata["project_ids"] == ["project-1", "project-2"]

    standard_result = await manager.update_glossary_metadata(
        glossary_id,
        name="Shared Mod Terms",
        description="No longer project-bound.",
        kind="standard",
        project_ids=[],
    )
    assert standard_result["kind"] == "standard"
    assert standard_result["bound_projects"] == []

    async for session in db_manager.get_async_session():
        remaining_bindings = (await session.execute(
            select(ProjectGlossaryBinding).where(
                ProjectGlossaryBinding.glossary_id == glossary_id
            )
        )).scalars().all()
        break
    assert remaining_bindings == []


@pytest.mark.asyncio
async def test_update_glossary_metadata_rejects_second_main_glossary(glossary_database):
    async for session in db_manager.get_async_session():
        session.add_all([
            Glossary(game_id="vic3", name="Existing Main", is_main=True),
            Glossary(game_id="vic3", name="Candidate"),
        ])
        await session.commit()
        candidate = (await session.execute(
            select(Glossary).where(Glossary.name == "Candidate")
        )).scalar_one()
        candidate_id = candidate.glossary_id
        break

    with pytest.raises(ValueError, match="already has a main glossary"):
        await GlossaryManager().update_glossary_metadata(
            candidate_id,
            name="Candidate",
            kind="main",
            project_ids=[],
        )


@pytest.mark.asyncio
async def test_batch_delete_previews_risks_and_requires_explicit_confirmation(glossary_database):
    async for session in db_manager.get_async_session():
        main = Glossary(game_id="vic3", name="Main Terms", is_main=True)
        project_glossary = Glossary(
            game_id="vic3",
            name="Mod Terms",
            raw_metadata={"kind": "project_neologism_glossary", "owner_project_id": "p1"},
        )
        session.add_all([main, project_glossary])
        await session.flush()
        main_id = main.glossary_id
        project_id = project_glossary.glossary_id
        session.add(Project(
            project_id="p1",
            name="Victoria Mod",
            game_id="vic3",
            source_path="/tmp/p1",
            source_language="english",
        ))
        session.add(ProjectGlossaryBinding(project_id="p1", glossary_id=project_id))
        session.add_all([
            GlossaryEntry(entry_id="m1", glossary_id=main_id, translations={"en": "One"}),
            GlossaryEntry(entry_id="m2", glossary_id=main_id, translations={"en": "Two"}),
            GlossaryEntry(entry_id="p1", glossary_id=project_id, translations={"en": "Mod"}),
        ])
        await session.commit()
        break

    manager = GlossaryManager()
    impact = await manager.get_batch_delete_impact([main_id, project_id, 9999])

    assert impact["glossary_count"] == 2
    assert impact["term_count"] == 3
    assert [item["glossary_id"] for item in impact["main_glossaries"]] == [main_id]
    assert [item["glossary_id"] for item in impact["project_glossaries"]] == [project_id]
    assert impact["bound_projects"] == [{
        "project_id": "p1",
        "project_name": "Victoria Mod",
        "glossary_id": project_id,
        "glossary_name": "Mod Terms",
    }]
    assert impact["missing_glossary_ids"] == [9999]

    with pytest.raises(ValueError, match="no longer exist"):
        await manager.batch_delete_glossaries([main_id, project_id, 9999])
    with pytest.raises(ValueError, match="main glossary"):
        await manager.batch_delete_glossaries([main_id, project_id])
    with pytest.raises(ValueError, match="project-bound"):
        await manager.batch_delete_glossaries(
            [main_id, project_id],
            confirm_main_glossaries=True,
        )

    result = await manager.batch_delete_glossaries(
        [main_id, project_id],
        confirm_main_glossaries=True,
        confirm_project_bindings=True,
    )
    assert result == {
        "deleted_glossary_ids": [main_id, project_id],
        "deleted_glossary_count": 2,
        "deleted_term_count": 3,
        "removed_project_binding_count": 1,
    }

    async for session in db_manager.get_async_session():
        assert (await session.execute(select(Glossary))).scalars().all() == []
        assert (await session.execute(select(GlossaryEntry))).scalars().all() == []
        assert (await session.execute(select(ProjectGlossaryBinding))).scalars().all() == []
        break


@pytest.mark.asyncio
async def test_merge_preview_classifies_terms_and_execution_records_lineage(glossary_database):
    async for session in db_manager.get_async_session():
        first = Glossary(game_id="stellaris", name="First")
        second = Glossary(game_id="stellaris", name="Second")
        session.add_all([first, second])
        await session.flush()
        first_id = first.glossary_id
        second_id = second.glossary_id
        session.add_all([
            GlossaryEntry(
                entry_id="admiral-first",
                glossary_id=first_id,
                translations={"en": "Admiral", "zh-CN": "海军上将"},
                raw_metadata={"source_text": "Admiral", "source_lang": "en"},
            ),
            GlossaryEntry(
                entry_id="planet-first",
                glossary_id=first_id,
                translations={"en": "Planet $COUNT$", "zh-CN": "行星"},
                raw_metadata={"source_text": "Planet $COUNT$", "source_lang": "en"},
            ),
            GlossaryEntry(
                entry_id="admiral-second",
                glossary_id=second_id,
                translations={"en": "Admiral", "zh-CN": "舰队司令"},
                raw_metadata={"source_text": "Admiral", "source_lang": "en"},
            ),
            GlossaryEntry(
                entry_id="planet-second",
                glossary_id=second_id,
                translations={"en": "Planet $COUNT$", "zh-CN": "行星"},
                raw_metadata={"source_text": "Planet $COUNT$", "source_lang": "en"},
            ),
            GlossaryEntry(entry_id="empty-source", glossary_id=second_id),
        ])
        await session.commit()
        break

    manager = GlossaryManager()
    preview = await manager.preview_glossary_merge(
        [first_id, second_id],
        target_mode="new",
        target_name="Merged Terms",
        conflict_strategy="skip_conflicts",
    )

    assert preview["source_entry_count"] == 4
    assert preview["unique_term_count"] == 2
    assert preview["duplicate_term_count"] == 1
    assert preview["conflict_count"] == 1
    assert preview["empty_source_count"] == 1
    assert preview["planned_term_count"] == 1
    assert preview["conflicts"][0]["source"] == "Admiral"
    assert preview["mutations_applied"] is False

    result = await manager.merge_glossaries(
        [first_id, second_id],
        target_mode="new",
        target_name="Merged Terms",
        conflict_strategy="keep_first",
    )

    assert result["created_entry_count"] == 2
    assert result["conflict_count"] == 1
    assert result["duplicate_term_count"] == 1
    assert result["skipped_conflict_count"] == 0
    assert result["mutations_applied"] is True

    async for session in db_manager.get_async_session():
        merged = (await session.execute(
            select(Glossary).where(Glossary.glossary_id == result["glossary_id"])
        )).scalar_one()
        merged_entries = (await session.execute(
            select(GlossaryEntry).where(GlossaryEntry.glossary_id == result["glossary_id"])
        )).scalars().all()
        break

    assert [item["glossary_id"] for item in merged.raw_metadata["merged_from"]] == [
        first_id,
        second_id,
    ]
    admiral = next(entry for entry in merged_entries if entry.raw_metadata["source_text"] == "Admiral")
    assert admiral.translations["zh-CN"] == "海军上将"
    assert {item["entry_id"] for item in admiral.raw_metadata["merge_sources"]} == {
        "admiral-first",
        "admiral-second",
    }


@pytest.mark.asyncio
async def test_health_check_is_deterministic_read_only_and_evidence_bounded(glossary_database):
    async for session in db_manager.get_async_session():
        glossary = Glossary(game_id="vic3", name="Health Test")
        session.add(glossary)
        await session.flush()
        glossary_id = glossary.glossary_id
        session.add_all([
            GlossaryEntry(
                entry_id="token-a",
                glossary_id=glossary_id,
                translations={"en": "Army $COUNT$", "zh-CN": "陆军"},
                raw_metadata={"source_text": "Army $COUNT$", "source_lang": "en"},
            ),
            GlossaryEntry(
                entry_id="token-b",
                glossary_id=glossary_id,
                translations={"en": "Army $COUNT$", "zh-CN": "陆军"},
                raw_metadata={"source_text": "Army $COUNT$", "source_lang": "en"},
            ),
            GlossaryEntry(entry_id="empty", glossary_id=glossary_id),
        ])
        await session.commit()
        break

    report = await GlossaryManager().check_glossary_health(
        [glossary_id],
        target_lang="zh-CN",
    )

    codes = {issue["code"] for issue in report["issues"]}
    assert {"empty_source", "missing_translation", "placeholder_mismatch", "duplicate_term"} <= codes
    assert report["score"] < 100
    assert report["method"] == "deterministic"
    assert report["mutations_applied"] is False
    missing_translation = next(issue for issue in report["issues"] if issue["code"] == "missing_translation")
    assert missing_translation["items"][0]["game_id"] == "vic3"
    assert missing_translation["items"][0]["entry_id"] == "empty"
    focused = await GlossaryManager().search_glossary_entries_paginated(
        "empty", [glossary_id], page=1, page_size=25
    )
    assert [entry["entry_id"] for entry in focused["entries"]] == ["empty"]
    async for session in db_manager.get_async_session():
        assert len((await session.execute(select(GlossaryEntry))).scalars().all()) == 3
        break


@pytest.mark.asyncio
async def test_existing_target_merge_strategy_uses_selected_source_order(glossary_database):
    async for session in db_manager.get_async_session():
        first = Glossary(game_id="ck3", name="First Source")
        last = Glossary(game_id="ck3", name="Last Source")
        target = Glossary(game_id="ck3", name="Existing Target")
        session.add_all([first, last, target])
        await session.flush()
        first_id, last_id, target_id = first.glossary_id, last.glossary_id, target.glossary_id
        session.add_all([
            GlossaryEntry(
                entry_id="first-ruler",
                glossary_id=first_id,
                translations={"en": "Ruler", "zh-CN": "统治者"},
                raw_metadata={"source_text": "Ruler"},
            ),
            GlossaryEntry(
                entry_id="last-ruler",
                glossary_id=last_id,
                translations={"en": "Ruler", "zh-CN": "领主"},
                raw_metadata={"source_text": "Ruler"},
            ),
            GlossaryEntry(
                entry_id="target-ruler",
                glossary_id=target_id,
                translations={"en": "Ruler", "zh-CN": "君主"},
                raw_metadata={"source_text": "Ruler"},
            ),
            GlossaryEntry(
                entry_id="target-only",
                glossary_id=target_id,
                translations={"en": "Vassal", "zh-CN": "封臣"},
                raw_metadata={"source_text": "Vassal"},
            ),
        ])
        await session.commit()
        break

    result = await GlossaryManager().merge_glossaries(
        [first_id, last_id],
        target_mode="existing",
        target_glossary_id=target_id,
        conflict_strategy="keep_last",
    )

    assert result["updated_entry_count"] == 1
    async for session in db_manager.get_async_session():
        entries = (await session.execute(
            select(GlossaryEntry).where(GlossaryEntry.glossary_id == target_id)
        )).scalars().all()
        break
    by_id = {entry.entry_id: entry for entry in entries}
    assert by_id["target-ruler"].translations["zh-CN"] == "领主"
    assert by_id["target-only"].translations["zh-CN"] == "封臣"
