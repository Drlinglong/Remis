import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scripts.core.services.translation_resource_policy import (
    resolve_translation_resource_policy,
    resolve_translation_run_resources,
)
from scripts.core.services import initial_translation_workspace_service


def test_explicit_translation_context_modes_are_mutually_exclusive():
    none = resolve_translation_resource_policy(
        "none",
        legacy_use_main_glossary=True,
        legacy_use_project_context=True,
    )
    glossaries = resolve_translation_resource_policy(
        "glossaries",
        legacy_use_main_glossary=False,
        legacy_use_project_context=True,
    )
    archive = resolve_translation_resource_policy(
        "archive",
        legacy_use_main_glossary=False,
        legacy_use_project_context=False,
    )

    assert none.use_glossaries is False
    assert none.include_project_context is False
    assert glossaries.use_glossaries is True
    assert glossaries.include_project_context is False
    assert archive.use_glossaries is True
    assert archive.include_project_context is True


def test_none_mode_still_resolves_the_project_path_without_loading_glossaries():
    project_manager = SimpleNamespace(
        get_project=AsyncMock(return_value={"source_path": "J:/mods/example"})
    )
    glossary_manager = SimpleNamespace(
        get_available_glossaries=AsyncMock(),
        get_project_glossary=AsyncMock(),
    )

    resources = resolve_translation_run_resources(
        game_id="stellaris",
        project_id="project-1",
        selected_glossary_ids=[99],
        mode="none",
        legacy_use_main_glossary=True,
        legacy_use_project_context=True,
        project_manager=project_manager,
        glossary_manager=glossary_manager,
        run_async=asyncio.run,
    )

    assert resources.override_path == "J:/mods/example"
    assert resources.glossary_ids == ()
    glossary_manager.get_available_glossaries.assert_not_called()
    glossary_manager.get_project_glossary.assert_not_called()


def test_archive_mode_orders_main_project_and_explicit_glossaries():
    project_manager = SimpleNamespace(
        get_project=AsyncMock(
            return_value={"source_path": "J:/mods/example", "name": "Example"}
        )
    )
    glossary_manager = SimpleNamespace(
        get_available_glossaries=AsyncMock(
            return_value=[{"glossary_id": 10, "is_main": True}]
        ),
        get_project_glossary=AsyncMock(return_value={"glossary_id": 20}),
    )

    resources = resolve_translation_run_resources(
        game_id="stellaris",
        project_id="project-1",
        selected_glossary_ids=[20, 30],
        mode="archive",
        legacy_use_main_glossary=False,
        legacy_use_project_context=False,
        project_manager=project_manager,
        glossary_manager=glossary_manager,
        run_async=asyncio.run,
    )

    assert resources.glossary_ids == (10, 20, 30)
    assert resources.policy.include_project_context is True


def test_no_glossary_mode_clears_previous_in_memory_entries(monkeypatch):
    manager = SimpleNamespace(load_selected_glossaries=AsyncMock(return_value=True))
    monkeypatch.setattr(initial_translation_workspace_service, "glossary_manager", manager)

    initial_translation_workspace_service.load_glossaries_for_run(
        "stellaris",
        False,
        [10],
    )

    manager.load_selected_glossaries.assert_awaited_once_with([])
