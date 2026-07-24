import asyncio

import pytest

from scripts.core.db_models import Glossary
from scripts.core.glossary_manager import GlossaryManager


@pytest.mark.asyncio
async def test_get_or_create_project_glossary_serializes_first_creation(monkeypatch):
    manager = GlossaryManager()
    created = {"glossary": None, "count": 0}

    async def get_project_glossary(*_args):
        return created["glossary"]

    class FakeSession:
        def add(self, value):
            if isinstance(value, Glossary):
                created["count"] += 1
                value.glossary_id = 41
                created["glossary"] = value.model_dump()

        async def commit(self):
            await asyncio.sleep(0)

        async def refresh(self, _value):
            return None

    async def get_async_session():
        yield FakeSession()

    monkeypatch.setattr(manager, "get_project_glossary", get_project_glossary)
    monkeypatch.setattr(manager.db_manager, "get_async_session", get_async_session)

    first, second = await asyncio.gather(
        manager.get_or_create_project_glossary("stellaris", "project-1", "Demo"),
        manager.get_or_create_project_glossary("stellaris", "project-1", "Demo"),
    )

    assert created["count"] == 1
    assert first["glossary_id"] == 41
    assert second["glossary_id"] == 41
