import datetime
import logging
from typing import List, Optional, Dict, Any, Sequence
from contextlib import asynccontextmanager
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from scripts.core.db_models import Project, ProjectFile, ProjectHistory
from scripts.app_settings import PROJECTS_DB_PATH, relativize_path, resolve_path
import uuid

logger = logging.getLogger(__name__)

def normalize_project_file_status(status: Optional[str]) -> Optional[str]:
    """Map legacy file statuses onto the canonical project workflow columns."""
    if status == "translated":
        return "done"
    return status


class ProjectRepository:
    """
    Persistence layer for Projects and Project Files using Async SQLModel.
    Isolates all SQL logic from the business logic.
    Returns Pydantic Models (Project, ProjectFile) where applicable.
    """
    
    def __init__(self, db_path: str = PROJECTS_DB_PATH):
        self.db_path = db_path

    @asynccontextmanager
    async def _use_session(self, session: Optional[AsyncSession] = None):
        if session is not None:
            yield session
        else:
            from scripts.core.db_manager import db_manager
            async for local_session in db_manager.get_async_session():
                local_session.info["_remis_repository_owns_session"] = True
                yield local_session
                break

    def _owns_session(self, session: AsyncSession) -> bool:
        return bool(session.info.get("_remis_repository_owns_session"))

    async def _commit_if_owner(self, session: AsyncSession):
        if self._owns_session(session):
            await session.commit()

    async def _rollback_if_owner(self, session: AsyncSession):
        if self._owns_session(session):
            await session.rollback()

    async def add_history_entry(self, project_id: str, action_type: str, description: str, snapshot_id: Optional[int] = None, extra_metadata: Optional[Dict[str, Any]] = None, session: Optional[AsyncSession] = None):
        """
        New Unified DB Way:
        1. Logs entry to ProjectHistory.
        2. Updates Project's last_activity fields for denormalized summary.
        """
        async with self._use_session(session) as session:
            try:
                # 1. Create History Entry
                history_entry = ProjectHistory(
                    history_id=str(uuid.uuid4()),
                    project_id=project_id,
                    timestamp=datetime.datetime.now().isoformat(),
                    action_type=action_type,
                    description=description,
                    snapshot_id=snapshot_id,
                    extra_metadata=extra_metadata
                )
                session.add(history_entry)

                # 2. Update Project Summary Fields
                stmt = select(Project).where(Project.project_id == project_id)
                res = await session.execute(stmt)
                project = res.scalar_one_or_none()
                if project:
                    project.last_activity_type = action_type
                    project.last_activity_desc = description[:200] # Truncate if too long
                    project.last_modified = datetime.datetime.now().isoformat()
                    session.add(project)

                await self._commit_if_owner(session)
            except Exception as e:
                await self._rollback_if_owner(session)
                logger.error(f"Failed to add history entry: {e}")
                raise e

    async def get_recent_logs(self, limit: int = 10, session: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
        """Retrieves the latest history events with project names."""
        async with self._use_session(session) as session:
            # Join ProjectHistory and Project to get project names
            # Use outerjoin to include history even if project was deleted
            stmt = select(ProjectHistory, Project.name.label("project_name")) \
                .outerjoin(Project, Project.project_id == ProjectHistory.project_id) \
                .order_by(col(ProjectHistory.timestamp).desc()) \
                .limit(limit)
            
            result = await session.execute(stmt)
            rows = result.all()
            
            # Map to list of dicts for UI compatibility
            recent_logs = []
            for history, p_name in rows:
                dump = history.model_dump()
                dump['project_name'] = p_name
                # Map 'action_type' to 'type' for UI compatibility if needed
                dump['type'] = history.action_type
                recent_logs.append(dump)
            return recent_logs

    # Removed add_project_history as it's folded into add_history_entry

    async def get_project_history(self, project_id: str, session: Optional[AsyncSession] = None) -> List[ProjectHistory]:
        """Retrieves history for a specific project, ordered by timestamp desc."""
        async with self._use_session(session) as session:
            stmt = select(ProjectHistory).where(ProjectHistory.project_id == project_id).order_by(col(ProjectHistory.timestamp).desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def delete_history_event(self, history_id: str, session: Optional[AsyncSession] = None):
        """Deletes a specific history event."""
        async with self._use_session(session) as session:
            try:
                stmt = select(ProjectHistory).where(ProjectHistory.history_id == history_id)
                result = await session.execute(stmt)
                history = result.scalar_one_or_none()
                if history:
                    await session.delete(history)
                    await self._commit_if_owner(session)
            except Exception as e:
                await self._rollback_if_owner(session)
                logger.error(f"Failed to delete history event: {e}")
                raise e

    # --- Project CRUD ---

    async def get_project(self, project_id: str, session: Optional[AsyncSession] = None) -> Optional[Project]:
        async with self._use_session(session) as session:
            start_q = select(Project).where(Project.project_id == project_id)
            result = await session.execute(start_q)
            project = result.scalar_one_or_none()
            if project:
                project.source_path = resolve_path(project.source_path)
                project.target_path = resolve_path(project.target_path)
            return project

    async def list_projects(self, status: Optional[str] = None, session: Optional[AsyncSession] = None) -> List[Project]:
        async with self._use_session(session) as session:
            query = select(Project)
            if status:
                query = query.where(Project.status == status)
            query = query.order_by(col(Project.last_modified).desc())
            
            result = await session.execute(query)
            projects = list(result.scalars().all())
            for p in projects:
                p.source_path = resolve_path(p.source_path)
                p.target_path = resolve_path(p.target_path)
            return projects

    async def create_project(self, project_data: Project, session: Optional[AsyncSession] = None) -> Project:
        async with self._use_session(session) as session:
            try:
                db_project = project_data.model_copy(update={
                    "source_path": relativize_path(project_data.source_path),
                    "target_path": relativize_path(project_data.target_path),
                })
                session.add(db_project)
                await self._commit_if_owner(session)
                if self._owns_session(session):
                    await session.refresh(db_project)
                return db_project.model_copy(update={
                    "source_path": resolve_path(db_project.source_path),
                    "target_path": resolve_path(db_project.target_path),
                })
            except Exception as e:
                await self._rollback_if_owner(session)
                raise e

    async def update_project_status(self, project_id: str, status: str, session: Optional[AsyncSession] = None):
        async with self._use_session(session) as session:
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.status = status
                project.last_modified = current_time
                session.add(project)
                await self._commit_if_owner(session)

    async def update_project_notes(self, project_id: str, notes: str, session: Optional[AsyncSession] = None):
        """Persists project notes to the database and updates last_modified."""
        async with self._use_session(session) as session:
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.notes = notes
                project.last_modified = current_time
                session.add(project)
                await self._commit_if_owner(session)

    async def touch_project(self, project_id: str, session: Optional[AsyncSession] = None):
        """Updates the last_modified timestamp for a project."""
        async with self._use_session(session) as session:
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.last_modified = current_time
                session.add(project)
                await self._commit_if_owner(session)

    async def update_project_metadata(self, project_id: str, game_id: str, source_language: str, session: Optional[AsyncSession] = None):
        async with self._use_session(session) as session:
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.game_id = game_id
                project.source_language = source_language
                project.last_modified = current_time
                session.add(project)
                await self._commit_if_owner(session)

    async def update_project_source_path(self, project_id: str, source_path: str, session: Optional[AsyncSession] = None):
        async with self._use_session(session) as session:
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.source_path = relativize_path(source_path)
                project.last_modified = current_time
                session.add(project)
                await self._commit_if_owner(session)

    async def delete_project(self, project_id: str, session: Optional[AsyncSession] = None):
        async with self._use_session(session) as session:
            try:
                # 1. Delete Files
                statement_files = select(ProjectFile).where(ProjectFile.project_id == project_id)
                results_files = await session.execute(statement_files)
                files = results_files.scalars().all()
                for f in files:
                    await session.delete(f)
                
                # 2. Delete Project
                statement_project = select(Project).where(Project.project_id == project_id)
                results_project = await session.execute(statement_project)
                project = results_project.scalar_one_or_none()
                if project:
                    await session.delete(project)
                
                await self._commit_if_owner(session)
            except Exception as e:
                await self._rollback_if_owner(session)
                raise e

    async def get_project_by_file_id(self, file_id: str, session: Optional[AsyncSession] = None) -> Optional[Dict[str, Any]]:
        async with self._use_session(session) as session:
            query = select(Project).join(ProjectFile).where(ProjectFile.file_id == file_id)
            result = await session.execute(query)
            project = result.scalar_one_or_none()
            if project:
                project.source_path = resolve_path(project.source_path)
                project.target_path = resolve_path(project.target_path)
                return project.model_dump()
            return None

    # --- File Operations (Async Batch) ---

    async def batch_upsert_files(self, project_files: List[Dict[str, Any]], session: Optional[AsyncSession] = None):
        """
        Upserts a batch of files. SQLModel doesn't support generic upsert easily across DBs,
        but since we are SQLite specific with async engine, we can use SQLite ON CONFLICT logic 
        via raw SQL or check-then-update.
        Given performance needs, raw SQL execute is best for batch upsert in SQLite.
        """
        if not project_files:
            return

        db_project_files = []
        for file_data in project_files:
            db_file_data = dict(file_data)
            if "file_path" in db_file_data:
                db_file_data["file_path"] = relativize_path(db_file_data["file_path"])
            db_project_files.append(db_file_data)

        from sqlalchemy import text
        
        async with self._use_session(session) as session:
            try:
                stmt = text('''
                    INSERT INTO project_files (file_id, project_id, file_path, status, original_key_count, line_count, file_type)
                    VALUES (:file_id, :project_id, :file_path, :status, :original_key_count, :line_count, :file_type)
                    ON CONFLICT(file_id) DO UPDATE SET
                        status = excluded.status,
                        line_count = excluded.line_count,
                        file_type = excluded.file_type,
                        file_path = excluded.file_path
                ''')
                
                logger.info(f"ProjectRepository: Upserting {len(db_project_files)} files for project {db_project_files[0].get('project_id')}")

                for db_file_data in db_project_files:
                    db_file_data["status"] = normalize_project_file_status(db_file_data.get("status"))
                await session.execute(stmt, db_project_files)
                await self._commit_if_owner(session)
                logger.info(f"ProjectRepository: Batch upsert committed successfully.")
            except Exception as e:
                logger.error(f"Batch upsert failed: {str(e)}", exc_info=True)
                await self._rollback_if_owner(session)
                raise e

    async def delete_files_by_ids(self, file_ids: List[str], session: Optional[AsyncSession] = None):
        if not file_ids: return
        from sqlalchemy import delete
        
        async with self._use_session(session) as session:
            try:
                stmt = delete(ProjectFile).where(col(ProjectFile.file_id).in_(file_ids))
                await session.execute(stmt)
                await self._commit_if_owner(session)
            except Exception as e:
                await self._rollback_if_owner(session)
                raise e

    async def update_file_status_by_id(self, file_id: str, status: str, session: Optional[AsyncSession] = None):
        status = normalize_project_file_status(status)
        async with self._use_session(session) as session:
            stmt = select(ProjectFile).where(ProjectFile.file_id == file_id)
            result = await session.execute(stmt)
            file_record = result.scalar_one_or_none()
            if file_record:
                file_record.status = status
                session.add(file_record)
                await self._commit_if_owner(session)

    async def get_project_file_ids(self, project_id: str, session: Optional[AsyncSession] = None) -> List[str]:
        async with self._use_session(session) as session:
            stmt = select(ProjectFile.file_id).where(ProjectFile.project_id == project_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_project_files(self, project_id: str, session: Optional[AsyncSession] = None) -> List[ProjectFile]:
        async with self._use_session(session) as session:
            stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
            result = await session.execute(stmt)
            files = list(result.scalars().all())
            for f in files:
                f.file_path = resolve_path(f.file_path)
            return files

    async def get_dashboard_stats(self, session: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        Retrieves aggregate statistics for the dashboard.
        """
        from sqlalchemy import func, text
        
        async with self._use_session(session) as session:
            # 1. Total Projects
            res = await session.execute(select(func.count(Project.project_id)))
            total_projects = res.scalar_one()
            
            # 2. Active Projects
            res = await session.execute(select(func.count(Project.project_id)).where(Project.status == 'active'))
            active_projects = res.scalar_one()
            
            # 3. File Statistics (by status)
            stmt = text("""
                SELECT status, COUNT(*) as count, SUM(original_key_count) as total_keys
                FROM project_files
                GROUP BY status
            """)
            result = await session.execute(stmt)
            file_stats = result.mappings().all()
            
            status_counts = {}
            status_keys = {}
            for row in file_stats:
                normalized_status = normalize_project_file_status(row['status'])
                status_counts[normalized_status] = status_counts.get(normalized_status, 0) + row['count']
                status_keys[normalized_status] = status_keys.get(normalized_status, 0) + (row['total_keys'] or 0)
            
            total_keys = sum(status_keys.values())
            translated_keys = status_keys.get('done', 0)
            
            completed_keys = status_keys.get('done', 0) + status_keys.get('proofreading', 0)
            completion_rate = (completed_keys / total_keys * 100) if total_keys > 0 else 0

            # 4. Game Distribution
            stmt = text("SELECT game_id, COUNT(*) as count FROM projects GROUP BY game_id")
            result = await session.execute(stmt)
            game_stats = result.mappings().all()
            game_distribution = [{"name": row['game_id'], "value": row['count']} for row in game_stats]
            
            return {
                "total_projects": total_projects,
                "active_projects": active_projects,
                "total_files": sum(status_counts.values()),
                "status_distribution": [
                    {"name": "todo", "value": status_counts.get('todo', 0)},
                    {"name": "in_progress", "value": status_counts.get('in_progress', 0)},
                    {"name": "proofreading", "value": status_counts.get('proofreading', 0)},
                    {"name": "paused", "value": status_counts.get('paused', 0)},
                    {"name": "done", "value": status_counts.get('done', 0)}
                ],
                "game_distribution": game_distribution,
                "total_keys": total_keys,
                "translated_keys": translated_keys,
                "translated_files": status_counts.get('done', 0),
                "completion_rate": round(completion_rate, 1)
            }
        return {
            "total_projects": 0,
            "active_projects": 0,
            "total_files": 0,
            "status_distribution": [
                {"name": "todo", "value": 0},
                {"name": "in_progress", "value": 0},
                {"name": "proofreading", "value": 0},
                {"name": "paused", "value": 0},
                {"name": "done", "value": 0}
            ],
            "game_distribution": [],
            "total_keys": 0,
            "translated_keys": 0,
            "translated_files": 0,
            "completion_rate": 0
        }
