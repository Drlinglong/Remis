import logging
import json
import re
import threading
import asyncio
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Any, Optional

from sqlalchemy.future import select
from sqlalchemy import func
from sqlmodel import select as sqlmodel_select
from sqlmodel.ext.asyncio.session import AsyncSession

from scripts import app_settings
from scripts.utils import i18n
from scripts.utils.phonetics_engine import PhoneticsEngine
from scripts.core.db_manager import DatabaseConnectionManager
from scripts.core.db_models import Glossary, GlossaryEntry, Project, ProjectGlossaryBinding
from scripts.core.glossary_health_service import (
    GlossaryHealthService,
    entry_source_text,
    normalized_entry_source,
    semantic_entry_payload,
)

logger = logging.getLogger(__name__)

class GlossaryManager:
    """Async Glossary Manager using SQLModel."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.current_game_id: Optional[str] = None
        self.in_memory_glossary: Dict[str, Any] = {'entries': []}
        self.fuzzy_matching_mode: str = 'loose'
        self.phonetics_engine = PhoneticsEngine()
        self.db_manager = DatabaseConnectionManager()
        self.health_service = GlossaryHealthService(self.db_manager)

    def _get_game_id_variants(self, game_id: str) -> List[str]:
        """Return the canonical game id plus legacy aliases that may exist in old glossary rows."""
        normalized = (game_id or "").strip().lower()
        canonical = app_settings.GAME_ID_ALIASES.get(normalized, normalized)
        variants = {normalized, canonical}
        variants.update(
            alias for alias, target in app_settings.GAME_ID_ALIASES.items()
            if target == canonical
        )
        return [variant for variant in variants if variant]

    @staticmethod
    def _get_glossary_kind(glossary: Glossary) -> str:
        metadata = glossary.raw_metadata or {}
        if glossary.is_main:
            return "main"
        if (
            metadata.get("kind") == "project_neologism_glossary"
            or bool(metadata.get("owner_project_id"))
        ):
            return "project"
        return "standard"

    async def get_available_glossaries(self, game_id: str) -> List[Dict]:
        """Async: Query available glossaries for a game."""
        try:
            async for session in self.db_manager.get_async_session():
                statement = select(Glossary).where(
                    Glossary.game_id.in_(self._get_game_id_variants(game_id))
                )
                results = await session.execute(statement)
                glossaries = results.scalars().all()
                return [g.model_dump() for g in glossaries]
        except Exception as e:
            logger.error(f"Failed to get available glossaries for {game_id}: {e}")
            return []
        return []

    async def get_all_glossaries(self) -> List[Dict]:
        """Async: Query all available glossaries."""
        try:
            async for session in self.db_manager.get_async_session():
                statement = select(Glossary).order_by(Glossary.game_id, Glossary.name)
                results = await session.execute(statement)
                glossaries = results.scalars().all()
                return [g.model_dump() for g in glossaries]
        except Exception as e:
            logger.error(f"Failed to get all glossaries: {e}")
            return []
        return []

    async def get_glossary_overview(self) -> Dict[str, Any]:
        """Return aggregate glossary inventory data without per-glossary queries."""
        try:
            async for session in self.db_manager.get_async_session():
                entry_counts = (
                    select(
                        GlossaryEntry.glossary_id,
                        func.count(GlossaryEntry.entry_id).label("entry_count"),
                    )
                    .group_by(GlossaryEntry.glossary_id)
                    .subquery()
                )
                glossary_result = await session.exec(
                    select(
                        Glossary,
                        func.coalesce(entry_counts.c.entry_count, 0).label("entry_count"),
                    )
                    .outerjoin(
                        entry_counts,
                        Glossary.glossary_id == entry_counts.c.glossary_id,
                    )
                    .order_by(Glossary.game_id, Glossary.name)
                )

                binding_result = await session.exec(
                    select(ProjectGlossaryBinding, Project)
                    .outerjoin(Project, Project.project_id == ProjectGlossaryBinding.project_id)
                    .order_by(ProjectGlossaryBinding.project_id)
                )
                bindings_by_glossary: Dict[int, List[Dict[str, Any]]] = {}
                for binding, project in binding_result.all():
                    bindings_by_glossary.setdefault(binding.glossary_id, []).append({
                        "project_id": binding.project_id,
                        "name": project.name if project else binding.project_id,
                        "game_id": project.game_id if project else None,
                    })

                glossaries = []
                for glossary, entry_count in glossary_result.all():
                    metadata = glossary.raw_metadata or {}
                    bound_projects = bindings_by_glossary.get(glossary.glossary_id, [])
                    kind = (
                        "main"
                        if glossary.is_main
                        else "project"
                        if bound_projects
                        else "standard"
                    )

                    updated_at = next(
                        (
                            metadata.get(key)
                            for key in ("updated_at", "last_updated_at", "modified_at")
                            if metadata.get(key)
                        ),
                        None,
                    )

                    glossaries.append({
                        **glossary.model_dump(),
                        "kind": kind,
                        "entry_count": int(entry_count or 0),
                        "bound_projects": bound_projects,
                        "updated_at": updated_at,
                    })

                return {
                    "summary": {
                        "game_count": len({item["game_id"] for item in glossaries}),
                        "glossary_count": len(glossaries),
                        "term_count": sum(item["entry_count"] for item in glossaries),
                        "main_glossary_count": sum(item["kind"] == "main" for item in glossaries),
                        "project_glossary_count": sum(item["kind"] == "project" for item in glossaries),
                        "bound_project_count": len({
                            project["project_id"]
                            for item in glossaries
                            for project in item["bound_projects"]
                        }),
                    },
                    "glossaries": glossaries,
                }
        except Exception as e:
            logger.error(f"Failed to build glossary overview: {e}")
            return {
                "summary": {
                    "game_count": 0,
                    "glossary_count": 0,
                    "term_count": 0,
                    "main_glossary_count": 0,
                    "project_glossary_count": 0,
                    "bound_project_count": 0,
                },
                "glossaries": [],
            }

        return {"summary": {}, "glossaries": []}

    def get_project_glossary_name(self, project_id: str, project_name: Optional[str] = None) -> str:
        """Return the deterministic glossary name reserved for a single project."""
        return project_name or f"Project Terms - {project_id}"

    async def get_project_glossary(self, game_id: str, project_id: str, project_name: Optional[str] = None) -> Optional[Dict]:
        """Async: Return the preferred dedicated glossary for a project if one exists."""
        try:
            async for session in self.db_manager.get_async_session():
                binding_result = await session.execute(
                    select(ProjectGlossaryBinding, Glossary)
                    .join(Glossary, Glossary.glossary_id == ProjectGlossaryBinding.glossary_id)
                    .where(ProjectGlossaryBinding.project_id == project_id)
                    .order_by(ProjectGlossaryBinding.updated_at.desc())
                )
                bound_glossaries = [
                    glossary
                    for _binding, glossary in binding_result.all()
                    if glossary.game_id in self._get_game_id_variants(game_id)
                ]
                if bound_glossaries:
                    preferred = next(
                        (
                            glossary
                            for glossary in bound_glossaries
                            if (
                                (glossary.raw_metadata or {}).get("kind")
                                == "project_neologism_glossary"
                                and (glossary.raw_metadata or {}).get("owner_project_id")
                                == project_id
                            )
                        ),
                        bound_glossaries[0],
                    )
                    return preferred.model_dump()

                statement = select(Glossary).where(
                    Glossary.is_main == False,
                )
                result = await session.execute(statement)
                glossaries = result.scalars().all()
                glossary = next(
                    (
                        g for g in glossaries
                        if (g.raw_metadata or {}).get("kind") == "project_neologism_glossary"
                        and (g.raw_metadata or {}).get("project_id") == project_id
                    ),
                    None,
                )
                return glossary.model_dump() if glossary else None
        except Exception as e:
            logger.error(f"Failed to get project glossary for {project_id}: {e}")
            return None
        return None

    async def get_glossary_by_id(self, glossary_id: int) -> Optional[Dict]:
        """Async: Return a glossary by ID."""
        try:
            async for session in self.db_manager.get_async_session():
                statement = select(Glossary).where(Glossary.glossary_id == glossary_id)
                result = await session.execute(statement)
                glossary = result.scalar_one_or_none()
                return glossary.model_dump() if glossary else None
        except Exception as e:
            logger.error(f"Failed to get glossary {glossary_id}: {e}")
            return None
        return None

    def _clear_project_glossary_binding(self, glossary: Glossary) -> None:
        metadata = dict(glossary.raw_metadata or {})
        for key in (
            "kind",
            "owner_project_id",
            "owner_project_ids",
            "project_id",
            "project_ids",
            "project_name",
        ):
            metadata.pop(key, None)
        glossary.raw_metadata = metadata

    async def bind_project_glossary(self, game_id: str, project_id: str, project_name: Optional[str], glossary_id: int) -> Optional[Dict]:
        """Async: Bind one glossary to a project."""
        try:
            async for session in self.db_manager.get_async_session():
                target_result = await session.execute(
                    select(Glossary).where(Glossary.glossary_id == glossary_id)
                )
                target = target_result.scalar_one_or_none()
                if not target:
                    return None
                if target.is_main:
                    raise ValueError("A main glossary cannot also be project-specific.")
                if target.game_id not in self._get_game_id_variants(game_id):
                    raise ValueError("Glossary and project must belong to the same game.")

                now = datetime.now().isoformat()
                binding_result = await session.execute(
                    select(ProjectGlossaryBinding).where(
                        ProjectGlossaryBinding.project_id == project_id,
                        ProjectGlossaryBinding.glossary_id == glossary_id,
                    )
                )
                binding = binding_result.scalar_one_or_none()
                if binding:
                    binding.updated_at = now
                else:
                    binding = ProjectGlossaryBinding(
                        project_id=project_id,
                        glossary_id=glossary_id,
                        created_at=now,
                        updated_at=now,
                    )
                metadata = deepcopy(target.raw_metadata or {})
                metadata.setdefault("kind", "project_glossary")
                project_ids = set(metadata.get("project_ids") or [])
                project_ids.add(project_id)
                metadata["project_ids"] = sorted(project_ids)
                metadata["updated_at"] = now
                target.raw_metadata = metadata
                session.add(binding)
                session.add(target)
                await session.commit()
                await session.refresh(target)
                return target.model_dump()
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to bind project glossary {glossary_id} to {project_id}: {e}")
            return None
        return None

    async def unbind_project_glossary(self, game_id: str, project_id: str) -> bool:
        """Async: Remove the preferred glossary binding currently shown for a project."""
        try:
            async for session in self.db_manager.get_async_session():
                binding_result = await session.execute(
                    select(ProjectGlossaryBinding, Glossary)
                    .join(Glossary, Glossary.glossary_id == ProjectGlossaryBinding.glossary_id)
                    .where(ProjectGlossaryBinding.project_id == project_id)
                    .order_by(ProjectGlossaryBinding.updated_at.desc())
                )
                bound_rows = binding_result.all()
                selected_row = next(
                    (
                        row for row in bound_rows
                        if (
                            (row[1].raw_metadata or {}).get("kind")
                            == "project_neologism_glossary"
                            and (row[1].raw_metadata or {}).get("owner_project_id")
                            == project_id
                        )
                    ),
                    bound_rows[0] if bound_rows else None,
                )
                binding = selected_row[0] if selected_row else None
                selected_glossary = selected_row[1] if selected_row else None
                if binding is not None:
                    await session.delete(binding)

                changed = False
                if selected_glossary is not None:
                    remaining_result = await session.execute(
                        select(ProjectGlossaryBinding).where(
                            ProjectGlossaryBinding.glossary_id
                            == selected_glossary.glossary_id,
                            ProjectGlossaryBinding.project_id != project_id,
                        )
                    )
                    remaining_project_ids = {
                        item.project_id for item in remaining_result.scalars().all()
                    }
                    if remaining_project_ids:
                        metadata = deepcopy(selected_glossary.raw_metadata or {})
                        metadata["project_ids"] = sorted(remaining_project_ids)
                        selected_glossary.raw_metadata = metadata
                    else:
                        self._clear_project_glossary_binding(selected_glossary)
                    session.add(selected_glossary)
                    changed = True
                elif not bound_rows:
                    result = await session.execute(select(Glossary))
                    for glossary in result.scalars().all():
                        metadata = glossary.raw_metadata or {}
                        if (
                            metadata.get("kind") == "project_neologism_glossary"
                            and (
                                metadata.get("project_id") == project_id
                                or metadata.get("owner_project_id") == project_id
                            )
                        ):
                            self._clear_project_glossary_binding(glossary)
                            session.add(glossary)
                            changed = True
                if changed or binding:
                    await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to unbind project glossary for {project_id}: {e}")
            return False
        return False

    async def get_or_create_project_glossary(self, game_id: str, project_id: str, project_name: Optional[str] = None) -> Optional[Dict]:
        """Async: Ensure the dedicated glossary for a project exists and return it."""
        existing = await self.get_project_glossary(game_id, project_id, project_name)
        if existing:
            return existing

        try:
            async for session in self.db_manager.get_async_session():
                glossary = Glossary(
                    game_id=game_id,
                    name=self.get_project_glossary_name(project_id, project_name),
                    description=f"Auto-mined project glossary for {project_name or project_id}",
                    is_main=False,
                    raw_metadata={
                        "kind": "project_neologism_glossary",
                        "owner_project_id": project_id,
                        "project_name": project_name,
                    },
                )
                session.add(glossary)
                await session.commit()
                await session.refresh(glossary)
                now = datetime.now().isoformat()
                session.add(ProjectGlossaryBinding(
                    project_id=project_id,
                    glossary_id=glossary.glossary_id,
                    created_at=now,
                    updated_at=now,
                ))
                await session.commit()
                return glossary.model_dump()
        except Exception as e:
            logger.error(f"Failed to create project glossary for {project_id}: {e}")
            return None
        return None

    async def get_entries_for_glossary_ids(self, glossary_ids: List[int]) -> List[Dict]:
        """Async: Return all entries from a small set of glossaries."""
        if not glossary_ids:
            return []
        try:
            async for session in self.db_manager.get_async_session():
                stmt = select(GlossaryEntry).where(GlossaryEntry.glossary_id.in_(glossary_ids))
                results = await session.execute(stmt)
                return [entry.model_dump() for entry in results.scalars().all()]
        except Exception as e:
            logger.error(f"Failed to get glossary entries for {glossary_ids}: {e}")
            return []
        return []

    async def get_glossary_tree_data(self) -> List[Dict]:
        """Async: Build glossary tree data."""
        try:
            async for session in self.db_manager.get_async_session():
                statement = select(Glossary).order_by(Glossary.game_id, Glossary.name)
                results = await session.execute(statement)
                glossaries = results.scalars().all()

                tree_data = []
                current_game_id = None
                game_node = None

                for g in glossaries:
                    if g.game_id != current_game_id:
                        if game_node:
                            tree_data.append(game_node)
                        current_game_id = g.game_id
                        game_node = {
                            "title": current_game_id,
                            "key": current_game_id,
                            "children": []
                        }
                    
                    if game_node:
                        game_node["children"].append({
                            "title": g.name,
                            "key": f"{g.game_id}|{g.glossary_id}|{g.name}",
                            "isLeaf": True
                        })
                
                if game_node:
                    tree_data.append(game_node)
                    
                return tree_data
        except Exception as e:
            logger.error(f"Failed to build glossary tree: {e}")
            return []
        return []

    async def get_glossary_entries_paginated(self, glossary_id: int, page: int, page_size: int) -> Dict:
        """Async: Get paginated entries."""
        try:
            async for session in self.db_manager.get_async_session():
                # Count
                count_stmt = select(func.count()).select_from(GlossaryEntry).where(GlossaryEntry.glossary_id == glossary_id)
                total_count = (await session.execute(count_stmt)).scalar_one()

                # Select
                offset = (page - 1) * page_size
                stmt = select(GlossaryEntry).where(GlossaryEntry.glossary_id == glossary_id).limit(page_size).offset(offset)
                results = await session.execute(stmt)
                entries = results.scalars().all()
                
                return {
                    "entries": [e.model_dump() for e in entries],
                    "totalCount": total_count
                }
        except Exception as e:
            logger.error(f"Failed to get entries for {glossary_id}: {e}")
            return {"entries": [], "totalCount": 0}
        return {"entries": [], "totalCount": 0}

    async def search_glossary_entries_paginated(self, query: str, glossary_ids: List[int], page: int, page_size: int) -> Dict:
        """Async: Search entries."""
        if not glossary_ids:
            return {"entries": [], "totalCount": 0}

        try:
            async for session in self.db_manager.get_async_session():
                # Search using JSON casting or text text query is tricky in SQLModel + SQLite JSON
                # But here we search in 'translations' column which is JSON type.
                # In SQLite, we can use LIKE on the text representation of JSON?
                # SQLAlchemy JSON type handles serialization. In SQLite it's TEXT.
                # So `cast(GlossaryEntry.translations, String).ilike(f"%{query}%")` might work.
                # However, cleaner is just `GlossaryEntry.translations.ilike(...)`? No.
                
                from sqlalchemy import cast, String
                
                search_term = f"%{query.lower()}%"
                
                # Base condition
                # Note: This crude casting relies on backend storing JSON as string.
                condition = (GlossaryEntry.glossary_id.in_(glossary_ids)) & (
                    cast(GlossaryEntry.translations, String).ilike(search_term)
                    | cast(GlossaryEntry.raw_metadata, String).ilike(search_term)
                    | GlossaryEntry.entry_id.ilike(search_term)
                )

                # Count
                count_stmt = select(func.count()).select_from(GlossaryEntry).where(condition)
                total_count = (await session.execute(count_stmt)).scalar_one()

                # Select
                offset = (page - 1) * page_size
                stmt = select(GlossaryEntry).where(condition).limit(page_size).offset(offset)
                results = await session.execute(stmt)
                entries = results.scalars().all()

                return {
                    "entries": [e.model_dump() for e in entries],
                    "totalCount": total_count
                }
        except Exception as e:
            logger.error(f"Failed to search entries: {e}")
            return {"entries": [], "totalCount": 0}
        return {"entries": [], "totalCount": 0}

    async def load_game_glossary(self, game_id: str) -> bool:
        """Async: Load main glossary for a game into memory."""
        self.current_game_id = game_id
        try:
            async for session in self.db_manager.get_async_session():
                # Find main glossary
                stmt = select(Glossary).where(Glossary.game_id == game_id, Glossary.is_main == True)
                result = await session.execute(stmt)
                main_glossary = result.scalar_one_or_none()

                if main_glossary and main_glossary.glossary_id:
                     return await self.load_selected_glossaries([main_glossary.glossary_id])
                else:
                    logger.warning(f"No main glossary found for {game_id}")
                    with self._lock:
                        self.in_memory_glossary = {'entries': []}
                    return False
        except Exception as e:
            logger.error(f"Error loading main glossary for {game_id}: {e}")
            return False
        return False

    async def load_selected_glossaries(self, selected_glossary_ids: List[int]) -> bool:
        """Async: Load glossaries from low to high priority into memory."""
        if not selected_glossary_ids:
            with self._lock:
                self.in_memory_glossary = {'entries': []}
            return True

        try:
            async for session in self.db_manager.get_async_session():
                stmt = select(GlossaryEntry).where(GlossaryEntry.glossary_id.in_(selected_glossary_ids))
                results = await session.execute(stmt)
                entries = results.scalars().all()
                
                priority_by_id = {
                    glossary_id: priority
                    for priority, glossary_id in enumerate(selected_glossary_ids)
                }
                entries_data = []
                for entry in entries:
                    entry_data = entry.model_dump()
                    entry_data["_glossary_priority"] = priority_by_id.get(entry.glossary_id, -1)
                    entries_data.append(entry_data)
                
                with self._lock:
                    self.in_memory_glossary = {'entries': entries_data}
                
                logger.info(i18n.t("log_glossary_loaded_from_selected", entries_count=len(entries_data), glossaries_count=len(selected_glossary_ids)))
                return True
        except Exception as e:
            logger.error(f"Failed to load selected glossaries: {e}")
            with self._lock:
                 self.in_memory_glossary = {'entries': []}
            return False
        return False

    async def add_entry(self, glossary_id: int, entry_data: Dict) -> bool:
        """Async: Add or Replace entry."""
        try:
            async for session in self.db_manager.get_async_session():
                # Check directly merging?
                # entry_data has 'id' which maps to 'entry_id'
                # But model expects 'entry_id'.
                
                # Transform data to model
                entry = GlossaryEntry(
                    entry_id=entry_data['id'],
                    glossary_id=glossary_id,
                    translations=entry_data.get('translations', {}),
                    abbreviations=entry_data.get('abbreviations', {}),
                    variants=entry_data.get('variants', {}),
                    raw_metadata=entry_data.get('metadata', {})
                )
                
                merged_entry = await session.merge(entry)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add entry: {e}")
            return False
        return False

    async def update_entry(self, entry_id: str, entry_data: Dict) -> bool:
        """Async: Update entry."""
        try:
            async for session in self.db_manager.get_async_session():
                stmt = select(GlossaryEntry).where(GlossaryEntry.entry_id == entry_id)
                result = await session.execute(stmt)
                entry = result.scalar_one_or_none()
                
                if entry:
                    entry.translations = entry_data.get('translations', {})
                    entry.abbreviations = entry_data.get('abbreviations', {})
                    entry.variants = entry_data.get('variants', {})
                    entry.raw_metadata = entry_data.get('metadata', {})
                    
                    session.add(entry)
                    await session.commit()
                    return True
                else:
                    logger.error(f"Entry {entry_id} not found for update")
                    return False
        except Exception as e:
            logger.error(f"Failed to update entry {entry_id}: {e}")
            return False
        return False

    async def delete_entry(self, entry_id: str) -> bool:
        """Async: Delete entry."""
        try:
            async for session in self.db_manager.get_async_session():
                stmt = select(GlossaryEntry).where(GlossaryEntry.entry_id == entry_id)
                result = await session.execute(stmt)
                entry = result.scalar_one_or_none()
                if entry:
                    await session.delete(entry)
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete entry {entry_id}: {e}")
            return False

    async def create_glossary_file(self, game_id: str, file_name: str) -> bool:
        """Async: Create new glossary."""
        try:
            async for session in self.db_manager.get_async_session():
                glossary = Glossary(
                    game_id=game_id,
                    name=file_name,
                    description=f"User created glossary for {game_id}",
                    is_main=False
                )
                session.add(glossary)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to create glossary file: {e}")
        return False

    async def update_glossary_metadata(
        self,
        glossary_id: int,
        *,
        name: str,
        description: str = "",
        kind: Optional[str] = None,
        project_ids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update glossary identity, type, and its many-to-many project bindings."""
        normalized_name = (name or "").strip()
        if not normalized_name:
            raise ValueError("Glossary name is required.")

        async for session in self.db_manager.get_async_session():
            glossary_result = await session.exec(
                sqlmodel_select(Glossary).where(Glossary.glossary_id == glossary_id)
            )
            glossary = glossary_result.first()
            if glossary is None:
                return None

            duplicate_result = await session.exec(
                sqlmodel_select(Glossary).where(
                    Glossary.glossary_id != glossary_id,
                    Glossary.game_id == glossary.game_id,
                    func.lower(Glossary.name) == normalized_name.lower(),
                )
            )
            if duplicate_result.first() is not None:
                raise ValueError(
                    f"A glossary named '{normalized_name}' already exists for {glossary.game_id}."
                )

            binding_result = await session.exec(
                sqlmodel_select(ProjectGlossaryBinding).where(
                    ProjectGlossaryBinding.glossary_id == glossary_id
                )
            )
            current_bindings = list(binding_result.all())
            current_project_ids = {binding.project_id for binding in current_bindings}
            relationships_requested = kind is not None or project_ids is not None
            target_kind = kind or self._get_glossary_kind(glossary)
            target_project_ids = (
                set(project_ids)
                if project_ids is not None
                else current_project_ids
            )

            if relationships_requested:
                if target_kind not in {"main", "project", "standard"}:
                    raise ValueError("Unknown glossary type.")
                if target_kind == "project" and not target_project_ids:
                    raise ValueError("A project glossary must be bound to at least one project.")
                if target_kind in {"main", "standard"} and target_project_ids:
                    raise ValueError("Main and standard glossaries cannot have project bindings.")

                if target_kind == "main":
                    existing_main_result = await session.exec(
                        sqlmodel_select(Glossary).where(
                            Glossary.glossary_id != glossary_id,
                            Glossary.game_id.in_(self._get_game_id_variants(glossary.game_id)),
                            Glossary.is_main == True,
                        )
                    )
                    existing_main = existing_main_result.first()
                    if existing_main is not None:
                        raise ValueError(
                            f"{glossary.game_id} already has a main glossary: {existing_main.name}."
                        )

            projects_by_id: Dict[str, Project] = {}
            if target_project_ids:
                project_result = await session.exec(
                    sqlmodel_select(Project).where(Project.project_id.in_(target_project_ids))
                )
                projects_by_id = {
                    project.project_id: project
                    for project in project_result.all()
                }
                missing_project_ids = sorted(target_project_ids - projects_by_id.keys())
                if relationships_requested and missing_project_ids:
                    raise ValueError(
                        "One or more selected projects no longer exist: "
                        + ", ".join(missing_project_ids)
                    )
                mismatched_projects = sorted(
                    project.name
                    for project in projects_by_id.values()
                    if project.game_id not in self._get_game_id_variants(glossary.game_id)
                )
                if relationships_requested and mismatched_projects:
                    raise ValueError(
                        "Glossaries can only bind projects from the same game: "
                        + ", ".join(mismatched_projects)
                    )

            updated_at = datetime.now().isoformat()
            metadata = deepcopy(glossary.raw_metadata or {})
            metadata["updated_at"] = updated_at
            glossary.name = normalized_name
            glossary.description = (description or "").strip() or None
            if relationships_requested:
                glossary.is_main = target_kind == "main"

                if target_kind == "project":
                    if metadata.get("kind") != "project_neologism_glossary":
                        metadata["kind"] = "project_glossary"
                    metadata["project_ids"] = sorted(target_project_ids)
                else:
                    self._clear_project_glossary_binding(glossary)
                    metadata = deepcopy(glossary.raw_metadata or {})
                    metadata["updated_at"] = updated_at

                for binding in current_bindings:
                    if binding.project_id not in target_project_ids:
                        await session.delete(binding)
                for project_id in sorted(target_project_ids - current_project_ids):
                    session.add(ProjectGlossaryBinding(
                        project_id=project_id,
                        glossary_id=glossary_id,
                        created_at=updated_at,
                        updated_at=updated_at,
                    ))

            glossary.raw_metadata = metadata

            session.add(glossary)
            await session.commit()

            return {
                "glossary_id": glossary.glossary_id,
                "game_id": glossary.game_id,
                "name": glossary.name,
                "description": glossary.description,
                "kind": target_kind,
                "bound_projects": [
                    {
                        "project_id": project_id,
                        "name": projects_by_id[project_id].name,
                        "game_id": projects_by_id[project_id].game_id,
                    }
                    for project_id in sorted(target_project_ids)
                    if project_id in projects_by_id
                ],
                "updated_at": updated_at,
            }

        return None

    async def duplicate_glossary(self, source_glossary_id: int, target_name: str) -> Optional[Dict[str, Any]]:
        """Create an independent glossary copy while preserving entry data and source lineage."""
        normalized_name = (target_name or "").strip()
        if not normalized_name:
            raise ValueError("Glossary name is required.")

        async for session in self.db_manager.get_async_session():
            source_result = await session.execute(
                select(Glossary).where(Glossary.glossary_id == source_glossary_id)
            )
            source = source_result.scalar_one_or_none()
            if source is None:
                return None

            duplicate_result = await session.execute(
                select(Glossary).where(
                    Glossary.game_id == source.game_id,
                    func.lower(Glossary.name) == normalized_name.lower(),
                )
            )
            if duplicate_result.scalar_one_or_none() is not None:
                raise ValueError(
                    f"A glossary named '{normalized_name}' already exists for {source.game_id}."
                )

            entry_result = await session.execute(
                select(GlossaryEntry).where(GlossaryEntry.glossary_id == source_glossary_id)
            )
            source_entries = entry_result.scalars().all()

            copied_at = datetime.now().isoformat()
            copied_metadata = deepcopy(source.raw_metadata or {})
            copied_metadata.pop("owner_project_id", None)
            copied_metadata.pop("project_id", None)
            if copied_metadata.get("kind") == "project_neologism_glossary":
                copied_metadata.pop("kind", None)
            copied_metadata["copied_from"] = {
                "glossary_id": source.glossary_id,
                "game_id": source.game_id,
                "name": source.name,
            }
            copied_metadata["copied_at"] = copied_at

            copied_glossary = Glossary(
                game_id=source.game_id,
                name=normalized_name,
                description=source.description,
                version=source.version,
                is_main=False,
                sources=deepcopy(source.sources or []),
                raw_metadata=copied_metadata,
            )
            session.add(copied_glossary)
            await session.flush()

            copied_entries = []
            for entry in source_entries:
                copied_entries.append(GlossaryEntry(
                    entry_id=str(uuid.uuid4()),
                    glossary_id=copied_glossary.glossary_id,
                    translations=deepcopy(entry.translations or {}),
                    abbreviations=deepcopy(entry.abbreviations or {}),
                    variants=deepcopy(entry.variants or {}),
                    raw_metadata=deepcopy(entry.raw_metadata or {}),
                ))

            session.add_all(copied_entries)
            await session.commit()

            return {
                "glossary_id": copied_glossary.glossary_id,
                "game_id": copied_glossary.game_id,
                "name": copied_glossary.name,
                "entry_count": len(copied_entries),
                "copied_from": copied_metadata["copied_from"],
            }

        return None

    @staticmethod
    def _entry_source_text(entry: GlossaryEntry) -> str:
        return entry_source_text(entry)

    @classmethod
    def _normalized_entry_source(cls, entry: GlossaryEntry) -> str:
        return normalized_entry_source(entry)

    @staticmethod
    def _semantic_entry_payload(entry: GlossaryEntry) -> Dict[str, Any]:
        return semantic_entry_payload(entry)

    async def _prepare_merge(
        self,
        session: AsyncSession,
        glossary_ids: List[int],
        *,
        target_mode: str,
        target_glossary_id: Optional[int],
        target_name: Optional[str],
    ) -> Dict[str, Any]:
        source_ids = list(dict.fromkeys(int(item) for item in glossary_ids))
        if len(source_ids) < 2:
            raise ValueError("Select at least two glossaries to merge.")

        requested_ids = list(source_ids)
        if target_mode == "existing" and target_glossary_id not in requested_ids:
            requested_ids.append(int(target_glossary_id))
        glossary_result = await session.execute(
            select(Glossary).where(Glossary.glossary_id.in_(requested_ids))
        )
        glossary_by_id = {
            glossary.glossary_id: glossary
            for glossary in glossary_result.scalars().all()
        }
        missing_ids = [item for item in requested_ids if item not in glossary_by_id]
        if missing_ids:
            raise ValueError("One or more selected glossaries no longer exist. Refresh and try again.")

        source_glossaries = [glossary_by_id[item] for item in source_ids]
        game_ids = {glossary.game_id for glossary in source_glossaries}
        target = glossary_by_id.get(target_glossary_id) if target_mode == "existing" else None
        if target is not None:
            game_ids.add(target.game_id)
        if len(game_ids) != 1:
            raise ValueError("Glossaries from different games cannot be merged.")

        normalized_target_name = (target_name or "").strip()
        if target_mode == "new":
            if not normalized_target_name:
                raise ValueError("A name is required for a new merged glossary.")
            collision_result = await session.execute(
                select(Glossary).where(
                    Glossary.game_id == source_glossaries[0].game_id,
                    func.lower(Glossary.name) == normalized_target_name.lower(),
                )
            )
            if collision_result.scalar_one_or_none() is not None:
                raise ValueError(
                    f"A glossary named '{normalized_target_name}' already exists for {source_glossaries[0].game_id}."
                )

        entry_glossary_ids = list(source_ids)
        if target is not None and target.glossary_id not in entry_glossary_ids:
            entry_glossary_ids.append(target.glossary_id)
        entry_result = await session.execute(
            select(GlossaryEntry).where(GlossaryEntry.glossary_id.in_(entry_glossary_ids))
        )
        priority_by_id = {glossary_id: index for index, glossary_id in enumerate(source_ids)}
        if target is not None and target.glossary_id not in priority_by_id:
            priority_by_id[target.glossary_id] = len(source_ids)
        entries = sorted(
            entry_result.scalars().all(),
            key=lambda entry: (priority_by_id[entry.glossary_id], entry.entry_id),
        )
        groups: Dict[str, List[GlossaryEntry]] = {}
        empty_source_entries: List[GlossaryEntry] = []
        for entry in entries:
            normalized_source = self._normalized_entry_source(entry)
            if not normalized_source:
                empty_source_entries.append(entry)
                continue
            groups.setdefault(normalized_source, []).append(entry)

        return {
            "source_ids": source_ids,
            "source_glossaries": source_glossaries,
            "target": target,
            "target_name": normalized_target_name,
            "glossary_by_id": glossary_by_id,
            "groups": groups,
            "empty_source_entries": empty_source_entries,
            "game_id": source_glossaries[0].game_id,
        }

    async def preview_glossary_merge(
        self,
        glossary_ids: List[int],
        *,
        target_mode: str,
        target_glossary_id: Optional[int] = None,
        target_name: Optional[str] = None,
        conflict_strategy: str = "skip_conflicts",
    ) -> Dict[str, Any]:
        """Build a read-only, deterministic merge plan before any glossary is changed."""
        async for session in self.db_manager.get_async_session():
            prepared = await self._prepare_merge(
                session,
                glossary_ids,
                target_mode=target_mode,
                target_glossary_id=target_glossary_id,
                target_name=target_name,
            )
            conflicts = []
            duplicate_term_count = 0
            for normalized_source, entries in prepared["groups"].items():
                fingerprints = {
                    json.dumps(self._semantic_entry_payload(entry), sort_keys=True, ensure_ascii=False)
                    for entry in entries
                }
                if len(fingerprints) == 1 and len(entries) > 1:
                    duplicate_term_count += 1
                if len(fingerprints) <= 1:
                    continue
                conflicts.append({
                    "source": self._entry_source_text(entries[0]),
                    "normalized_source": normalized_source,
                    "options": [
                        {
                            "entry_id": entry.entry_id,
                            "glossary_id": entry.glossary_id,
                            "glossary_name": prepared["glossary_by_id"][entry.glossary_id].name,
                            "translations": deepcopy(entry.translations or {}),
                        }
                        for entry in entries
                    ],
                })

            conflict_count = len(conflicts)
            planned_term_count = len(prepared["groups"])
            if conflict_strategy == "skip_conflicts":
                planned_term_count -= conflict_count
            return {
                "game_id": prepared["game_id"],
                "target_mode": target_mode,
                "target_glossary_id": target_glossary_id,
                "target_name": (
                    prepared["target"].name
                    if prepared["target"] is not None
                    else prepared["target_name"]
                ),
                "source_glossaries": [
                    {
                        "glossary_id": glossary.glossary_id,
                        "name": glossary.name,
                        "game_id": glossary.game_id,
                    }
                    for glossary in prepared["source_glossaries"]
                ],
                "source_entry_count": sum(len(items) for items in prepared["groups"].values()),
                "unique_term_count": len(prepared["groups"]),
                "duplicate_term_count": duplicate_term_count,
                "conflict_count": conflict_count,
                "empty_source_count": len(prepared["empty_source_entries"]),
                "planned_term_count": planned_term_count,
                "conflict_strategy": conflict_strategy,
                "conflicts": conflicts[:50],
                "conflicts_truncated": max(0, conflict_count - 50),
                "mutations_applied": False,
            }
        return {}

    async def merge_glossaries(
        self,
        glossary_ids: List[int],
        *,
        target_mode: str,
        target_glossary_id: Optional[int] = None,
        target_name: Optional[str] = None,
        conflict_strategy: str = "skip_conflicts",
    ) -> Dict[str, Any]:
        """Execute a previously previewable merge atomically and record entry lineage."""
        if conflict_strategy not in {"keep_first", "keep_last", "keep_target", "skip_conflicts"}:
            raise ValueError("Unknown merge conflict strategy.")
        if target_mode == "new" and conflict_strategy == "keep_target":
            raise ValueError("keep_target is only available for an existing target glossary.")

        async for session in self.db_manager.get_async_session():
            prepared = await self._prepare_merge(
                session,
                glossary_ids,
                target_mode=target_mode,
                target_glossary_id=target_glossary_id,
                target_name=target_name,
            )
            merged_at = datetime.now().isoformat()
            source_lineage = [
                {
                    "glossary_id": glossary.glossary_id,
                    "game_id": glossary.game_id,
                    "name": glossary.name,
                }
                for glossary in prepared["source_glossaries"]
            ]
            target = prepared["target"]
            if target is None:
                target = Glossary(
                    game_id=prepared["game_id"],
                    name=prepared["target_name"],
                    description="Merged glossary created by Remis",
                    is_main=False,
                    sources=list(dict.fromkeys(
                        source
                        for glossary in prepared["source_glossaries"]
                        for source in (glossary.sources or [])
                    )),
                    raw_metadata={
                        "merged_from": source_lineage,
                        "merged_at": merged_at,
                        "merge_conflict_strategy": conflict_strategy,
                    },
                )
                session.add(target)
                await session.flush()
            else:
                target_metadata = deepcopy(target.raw_metadata or {})
                target_metadata["merged_from"] = source_lineage
                target_metadata["merged_at"] = merged_at
                target_metadata["merge_conflict_strategy"] = conflict_strategy
                target_metadata["updated_at"] = merged_at
                target.raw_metadata = target_metadata
                session.add(target)

            created_count = 0
            updated_count = 0
            duplicate_term_count = 0
            conflict_count = 0
            skipped_conflict_count = 0
            for entries in prepared["groups"].values():
                if not any(entry.glossary_id in prepared["source_ids"] for entry in entries):
                    continue
                fingerprints = {
                    json.dumps(self._semantic_entry_payload(entry), sort_keys=True, ensure_ascii=False)
                    for entry in entries
                }
                is_conflict = len(fingerprints) > 1
                if is_conflict:
                    conflict_count += 1
                elif len(entries) > 1:
                    duplicate_term_count += 1

                target_entry = next(
                    (entry for entry in entries if entry.glossary_id == target.glossary_id),
                    None,
                )
                source_candidates = [
                    entry for entry in entries if entry.glossary_id in prepared["source_ids"]
                ]
                chosen: Optional[GlossaryEntry]
                if is_conflict and conflict_strategy == "skip_conflicts":
                    skipped_conflict_count += 1
                    continue
                if is_conflict and conflict_strategy == "keep_target" and target_entry is not None:
                    chosen = target_entry
                elif is_conflict and conflict_strategy == "keep_last":
                    chosen = source_candidates[-1]
                else:
                    chosen = source_candidates[0]

                lineage = [
                    {
                        "glossary_id": entry.glossary_id,
                        "glossary_name": prepared["glossary_by_id"][entry.glossary_id].name,
                        "entry_id": entry.entry_id,
                    }
                    for entry in entries
                ]
                merged_metadata = deepcopy(chosen.raw_metadata or {})
                merged_metadata["merge_sources"] = lineage
                merged_metadata["merged_at"] = merged_at

                if target_entry is not None:
                    if chosen.entry_id != target_entry.entry_id:
                        target_entry.translations = deepcopy(chosen.translations or {})
                        target_entry.abbreviations = deepcopy(chosen.abbreviations or {})
                        target_entry.variants = deepcopy(chosen.variants or {})
                    target_entry.raw_metadata = merged_metadata
                    session.add(target_entry)
                    updated_count += 1
                else:
                    session.add(GlossaryEntry(
                        entry_id=str(uuid.uuid4()),
                        glossary_id=target.glossary_id,
                        translations=deepcopy(chosen.translations or {}),
                        abbreviations=deepcopy(chosen.abbreviations or {}),
                        variants=deepcopy(chosen.variants or {}),
                        raw_metadata=merged_metadata,
                    ))
                    created_count += 1

            await session.commit()
            return {
                "glossary_id": target.glossary_id,
                "game_id": target.game_id,
                "name": target.name,
                "target_mode": target_mode,
                "created_entry_count": created_count,
                "updated_entry_count": updated_count,
                "duplicate_term_count": duplicate_term_count,
                "conflict_count": conflict_count,
                "skipped_conflict_count": skipped_conflict_count,
                "empty_source_count": len(prepared["empty_source_entries"]),
                "conflict_strategy": conflict_strategy,
                "merged_from": source_lineage,
                "mutations_applied": True,
            }
        return {}

    async def check_glossary_health(
        self,
        glossary_ids: List[int],
        *,
        target_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compatibility entry point for the dedicated read-only health service."""
        return await self.health_service.check(glossary_ids, target_lang=target_lang)

    async def get_batch_delete_impact(self, glossary_ids: List[int]) -> Dict[str, Any]:
        """Describe the exact glossary, term, main-glossary, and project-binding impact."""
        normalized_ids = list(dict.fromkeys(int(item) for item in glossary_ids))
        if not normalized_ids:
            raise ValueError("Select at least one glossary.")

        async for session in self.db_manager.get_async_session():
            entry_counts = (
                select(
                    GlossaryEntry.glossary_id,
                    func.count(GlossaryEntry.entry_id).label("entry_count"),
                )
                .where(GlossaryEntry.glossary_id.in_(normalized_ids))
                .group_by(GlossaryEntry.glossary_id)
                .subquery()
            )
            glossary_result = await session.execute(
                select(
                    Glossary,
                    func.coalesce(entry_counts.c.entry_count, 0).label("entry_count"),
                )
                .outerjoin(entry_counts, Glossary.glossary_id == entry_counts.c.glossary_id)
                .where(Glossary.glossary_id.in_(normalized_ids))
                .order_by(Glossary.game_id, Glossary.name)
            )
            rows = glossary_result.all()

            binding_result = await session.execute(
                select(ProjectGlossaryBinding, Project, Glossary)
                .join(Glossary, Glossary.glossary_id == ProjectGlossaryBinding.glossary_id)
                .outerjoin(Project, Project.project_id == ProjectGlossaryBinding.project_id)
                .where(ProjectGlossaryBinding.glossary_id.in_(normalized_ids))
                .order_by(ProjectGlossaryBinding.project_id)
            )

            glossaries = [
                {
                    "glossary_id": glossary.glossary_id,
                    "game_id": glossary.game_id,
                    "name": glossary.name,
                    "kind": self._get_glossary_kind(glossary),
                    "entry_count": int(entry_count or 0),
                }
                for glossary, entry_count in rows
            ]
            found_ids = {item["glossary_id"] for item in glossaries}
            bindings = [
                {
                    "project_id": binding.project_id,
                    "project_name": project.name if project else binding.project_id,
                    "glossary_id": glossary.glossary_id,
                    "glossary_name": glossary.name,
                }
                for binding, project, glossary in binding_result.all()
            ]

            return {
                "glossary_count": len(glossaries),
                "term_count": sum(item["entry_count"] for item in glossaries),
                "glossaries": glossaries,
                "main_glossaries": [item for item in glossaries if item["kind"] == "main"],
                "project_glossaries": [item for item in glossaries if item["kind"] == "project"],
                "bound_projects": bindings,
                "missing_glossary_ids": [
                    glossary_id for glossary_id in normalized_ids if glossary_id not in found_ids
                ],
            }

        return {}

    async def batch_delete_glossaries(
        self,
        glossary_ids: List[int],
        *,
        confirm_main_glossaries: bool = False,
        confirm_project_bindings: bool = False,
    ) -> Dict[str, Any]:
        """Delete a validated glossary selection atomically after explicit risk confirmation."""
        impact = await self.get_batch_delete_impact(glossary_ids)
        if impact["missing_glossary_ids"]:
            raise ValueError("One or more selected glossaries no longer exist. Refresh and try again.")
        if impact["main_glossaries"] and not confirm_main_glossaries:
            raise ValueError("Deleting a main glossary requires explicit confirmation.")
        if impact["bound_projects"] and not confirm_project_bindings:
            raise ValueError("Deleting project-bound glossaries requires explicit confirmation.")

        selected_ids = [item["glossary_id"] for item in impact["glossaries"]]
        from sqlalchemy import delete as sa_delete

        async for session in self.db_manager.get_async_session():
            await session.execute(
                sa_delete(GlossaryEntry).where(GlossaryEntry.glossary_id.in_(selected_ids))
            )
            await session.execute(
                sa_delete(ProjectGlossaryBinding).where(
                    ProjectGlossaryBinding.glossary_id.in_(selected_ids)
                )
            )
            await session.execute(
                sa_delete(Glossary).where(Glossary.glossary_id.in_(selected_ids))
            )
            await session.commit()
            return {
                "deleted_glossary_ids": selected_ids,
                "deleted_glossary_count": impact["glossary_count"],
                "deleted_term_count": impact["term_count"],
                "removed_project_binding_count": len(impact["bound_projects"]),
            }

        return {}

    async def delete_glossary(self, glossary_id: int) -> bool:
        """Async: Delete glossary and entries."""
        try:
            async for session in self.db_manager.get_async_session():
                # Delete entries first (cascade manual if not set in DB)
                from sqlalchemy import delete as sa_delete
                await session.execute(sa_delete(GlossaryEntry).where(GlossaryEntry.glossary_id == glossary_id))
                await session.execute(sa_delete(ProjectGlossaryBinding).where(ProjectGlossaryBinding.glossary_id == glossary_id))
                await session.execute(sa_delete(Glossary).where(Glossary.glossary_id == glossary_id))
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to delete glossary {glossary_id}: {e}")
            return False

    def get_glossary_for_translation(self) -> Optional[Dict]:
        """SYNC: Returns the in-memory glossary."""
        return self.in_memory_glossary if self.in_memory_glossary.get('entries') else None

    # --- Sync Business Logic (In-Memory) ---
    def extract_relevant_terms(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        glossary = self.get_glossary_for_translation()
        if not glossary or not glossary.get('entries'):
            return []
        
        logging.info(f"[Glossary] Extracting terms for {len(texts)} texts. Lang: {source_lang}->{target_lang}.")

        relevant_terms = []
        all_text = " ".join(texts).lower()
        matches = self._smart_term_matching(all_text, source_lang, target_lang)
        
        for match in matches:
            relevant_terms.append({
                'translations': {
                    source_lang: match['source_term'],
                    target_lang: match['target_term']
                },
                'id': match['id'],
                'metadata': match.get('metadata', match.get('raw_metadata', {})),
                'variants': match.get('variants', {}),
                'match_type': match['match_type'],
                'confidence': match['confidence']
            })
        relevant_terms.sort(key=lambda x: (x['confidence'], len(x['translations'][source_lang])), reverse=True)
        return relevant_terms

    def _smart_term_matching(self, text: str, source_lang: str, target_lang: str) -> List[Dict]:
        matches = []
        glossary = self.get_glossary_for_translation()
        if not glossary:
            return matches
            
        text_fingerprint = ""
        is_cjk = source_lang in ['zh-CN', 'zh-TW', 'ja', 'ko']
        if is_cjk:
            pe_lang = 'zh' if 'zh' in source_lang else source_lang
            text_fingerprint = self.phonetics_engine.generate_fingerprint(text, pe_lang)

        for entry in glossary.get('entries', []):
            translations = entry.get('translations', {})
            source_term = translations.get(source_lang, "")
            target_term = translations.get(target_lang, "")
            if not source_term or not target_term:
                continue
                
            # 1. Exact Match
            if source_term.lower() in text:
                matches.append(self._make_match(entry, source_term, target_term, 'exact', 1.0))
                continue
                
            # 2. Phonetic Match
            if is_cjk and len(source_term) > 1:
                term_fingerprint = self.phonetics_engine.generate_fingerprint(source_term, pe_lang)
                if term_fingerprint and term_fingerprint in text_fingerprint:
                    matches.append(self._make_match(entry, source_term, target_term, 'phonetic', 0.85))
                    continue

            # 3. Variant Match
            variants = entry.get('variants', {}).get(source_lang, [])
            found_variant = False
            for variant in variants:
                if variant.lower() in text:
                    matches.append(self._make_match(entry, source_term, target_term, 'variant', 0.9))
                    found_variant = True
                    break
            if found_variant: continue
            
            # 4. Abbreviation Match
            abbreviations = entry.get('abbreviations', {}).get(source_lang, [])
            if abbreviations:
                 for abbreviation in abbreviations:
                    if self._is_abbreviation_in_text(abbreviation, text, source_lang):
                         matches.append(self._make_match(entry, source_term, target_term, 'abbreviation', 0.85))
                         break
            
            # 5. Partial Match
            partial_match = self._check_partial_match(source_term, text, source_lang)
            if partial_match:
                 matches.append(self._make_match(entry, source_term, target_term, partial_match.get('match_type', 'partial'), partial_match['confidence']))

        return self._deduplicate_matches(matches)

    def _make_match(self, entry, source, target, mtype, conf):
        return {
            'source_term': source,
            'target_term': target,
            'id': entry.get('entry_id', ''),
            'metadata': entry.get('raw_metadata', {}),
            'variants': entry.get('variants', {}),
            'match_type': mtype,
            'confidence': conf,
            '_glossary_priority': entry.get('_glossary_priority', -1),
        }

    def create_dynamic_glossary_prompt(self, relevant_terms: List[Dict], source_lang: str, target_lang: str) -> str:
        if not relevant_terms:
            return ""
        prompt_lines = [
            "🔍 CONTEXT-AWARE GLOSSARY INSTRUCTIONS - HIGH PRIORITY 🔍",
            "The following entries are terminology candidates for this batch.",
            "Remarks define when a glossary translation applies; they are applicability conditions, not optional notes.",
            "",
            "Glossary Reference:"
        ]
        for term in relevant_terms:
            source = term['translations'][source_lang]
            target = term['translations'][target_lang]
            metadata = term.get('metadata', {})
            remarks = metadata.get('remarks', '')
            variants = term.get('variants', {}).get(source_lang, [])
            match_type = term.get('match_type', 'unknown')
            confidence = term.get('confidence', 1.0)
            
            match_info = f"[{match_type.upper()}]"
            if confidence < 1.0:
                 match_info += f" (confidence: {confidence:.1f})"
            
            prompt_lines.append(f"• {match_info} '{source}' → '{target}'")
            if variants:
                variant_list = ", ".join([f"'{v}'" for v in variants])
                prompt_lines.append(f"  Variants: {variant_list}")
            if remarks:
                 prompt_lines.append(f"  Remarks: {remarks}")
                 prompt_lines.append(
                     "  Scope: use the target translation only when the source context matches these Remarks."
                 )

        prompt_lines.extend([
            "",
            "Translation Requirements:",
            "1. When an entry has Remarks, use its target translation only when the source context matches those Remarks.",
            "2. If the context conflicts with the Remarks, choose the contextually correct translation instead of forcing the glossary target.",
            "3. When Remarks are absent, use exact unambiguous matches consistently; for polysemy or ambiguity, prefer the surrounding source context.",
            "4. Treat phonetic or fuzzy matches as references, not mandatory replacements.",
            "5. Do not add explanations to the translation output; preserve the required response format."
        ])
        return "\n".join(prompt_lines)

    def _check_partial_match(self, source_term: str, text: str, source_lang: str) -> Optional[Dict]:
        if len(source_term) > 3 and source_term.lower() in text:
            match_ratio = len(source_term) / len(text)
            if match_ratio > 0.3:
                return {'confidence': 0.7 + (match_ratio * 0.2)}
        fuzzy_match = self._check_fuzzy_match(source_term, text, source_lang)
        if fuzzy_match:
            return fuzzy_match
        return None

    def _check_fuzzy_match(self, source_term: str, text: str, source_lang: str) -> Optional[Dict]:
        if self.fuzzy_matching_mode == 'strict':
            return None
        text_tokens = self._tokenize_text(text, source_lang)
        source_tokens = self._tokenize_text(source_term, source_lang)
        if len(source_tokens) == 1:
            return self._check_single_word_fuzzy_match(source_term, text, source_lang)
        return self._check_multi_word_fuzzy_match(source_tokens, text_tokens, source_lang)

    def _check_single_word_fuzzy_match(self, source_term: str, text: str, source_lang: str) -> Optional[Dict]:
        if self._is_similar_word(source_term, text):
            distance = self._levenshtein_distance(source_term, text)
            max_distance = max(1, len(source_term) // 4)
            confidence = 0.6 - (distance / max_distance) * 0.3
            return {'confidence': confidence, 'match_type': 'fuzzy'}
        return None

    def _check_multi_word_fuzzy_match(self, source_tokens: List[str], text_tokens: List[str], source_lang: str) -> Optional[Dict]:
        matched_tokens = 0
        total_source_tokens = len(source_tokens)
        for source_token in source_tokens:
            if len(source_token) < 2: continue
            for text_token in text_tokens:
                if len(text_token) < 2: continue
                if source_token == text_token or self._is_similar_word(source_token, text_token):
                    matched_tokens += 1
                    break
        if matched_tokens > 0:
            match_ratio = matched_tokens / total_source_tokens
            if match_ratio > 0.5:
                confidence = 0.3 + (match_ratio * 0.3)
                return {'confidence': confidence, 'match_type': 'fuzzy'}
        return None

    def _tokenize_text(self, text: str, lang: str) -> List[str]:
        if lang in ['zh-CN', 'zh-TW', 'ja', 'ko']:
            return list(text)
        return re.findall(r'\w+', text.lower())

    def _is_similar_word(self, word1: str, word2: str) -> bool:
        if len(word1) < 3 or len(word2) < 3: return False
        distance = self._levenshtein_distance(word1, word2)
        max_distance = max(1, len(word1) // 4)
        return distance <= max_distance

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        if len(s1) < len(s2): return self._levenshtein_distance(s2, s1)
        if len(s2) == 0: return len(s1)
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def _is_abbreviation_in_text(self, abbreviation: str, text: str, source_lang: str) -> bool:
        if source_lang in ['en', 'fr', 'de', 'es']:
            pattern = r'\b' + re.escape(abbreviation.lower()) + r'\b'
            return bool(re.search(pattern, text.lower()))
        else:
            text_words = text.split()
            return abbreviation.lower() in [word.lower() for word in text_words]

    def _deduplicate_matches(self, matches: List[Dict]) -> List[Dict]:
        unique_matches = {}
        for match in matches:
            match_id = match['id']
            if match_id not in unique_matches or match['confidence'] > unique_matches[match_id]['confidence']:
                unique_matches[match_id] = match

        # The caller loads glossaries from low to high priority. A project glossary
        # therefore overrides a selected/game glossary, which overrides the main
        # glossary, for the same normalized source term.
        by_source = {}
        for match in unique_matches.values():
            source_key = " ".join((match.get('source_term') or '').casefold().split())
            current = by_source.get(source_key)
            candidate_rank = (match.get('_glossary_priority', -1), match.get('confidence', 0.0))
            current_rank = (
                current.get('_glossary_priority', -1),
                current.get('confidence', 0.0),
            ) if current else (-1, -1.0)
            if current is None or candidate_rank > current_rank:
                by_source[source_key] = match
        return list(by_source.values())
        
    async def get_glossary_stats(self) -> Dict[str, Any]:
        """Async: Get glossary statistics for dashboard (term counts per game)."""
        try:
            async for session in self.db_manager.get_async_session():
                # Count GlossaryEntries per Game
                # select glossary.game_id, count(entries.entry_id) as terms
                # from glossaries join entries on ... group by game_id
                stmt = select(Glossary.game_id, func.count(GlossaryEntry.entry_id).label('terms')) \
                    .join(GlossaryEntry, Glossary.glossary_id == GlossaryEntry.glossary_id) \
                    .group_by(Glossary.game_id)
                results = await session.execute(stmt)
                rows = results.all()
                
                game_distribution = [{"name": row[0], "terms": row[1]} for row in rows]
                
                return {
                    "game_distribution": game_distribution
                }
        except Exception as e:
            logger.error(f"Failed to get glossary stats: {e}")
            return {"game_distribution": []}
        return {"game_distribution": []}

    def set_fuzzy_matching_mode(self, mode: str):
        if mode in ['strict', 'loose']:
            self.fuzzy_matching_mode = mode
            logger.info(f"Fuzzy matching mode set to {mode}")
        else:
            self.fuzzy_matching_mode = 'loose'

glossary_manager = GlossaryManager()
