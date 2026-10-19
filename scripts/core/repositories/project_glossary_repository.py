"""Atomic creation and binding of dedicated project glossaries."""

from datetime import datetime
from scripts.core.db_models import Glossary, ProjectGlossaryBinding


async def ensure_bound_project_glossary(db_manager, game_id, project_id, name, existing=None, project_name=None):
    async for session in db_manager.get_async_session():
        try:
            if existing:
                glossary = await session.get(Glossary, existing["glossary_id"])
                if glossary is None:
                    raise ValueError("Project glossary disappeared before binding")
            else:
                glossary = Glossary(
                    game_id=game_id, name=name,
                    description=f"Auto-mined project glossary for {project_name or project_id}", is_main=False,
                    raw_metadata={"kind": "project_neologism_glossary",
                                  "owner_project_id": project_id, "project_name": project_name},
                )
                session.add(glossary)
                await session.flush()
            binding = await session.get(ProjectGlossaryBinding, (project_id, glossary.glossary_id))
            if binding is None:
                now = datetime.now().isoformat()
                session.add(ProjectGlossaryBinding(
                    project_id=project_id, glossary_id=glossary.glossary_id,
                    created_at=now, updated_at=now,
                ))
            await session.commit()
            return glossary.model_dump()
        except Exception:
            await session.rollback()
            raise
    return None
