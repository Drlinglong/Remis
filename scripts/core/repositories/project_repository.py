import datetime
import logging
from typing import List, Optional, Dict, Any, Sequence
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
from scripts.core.db_models import Project, ProjectFile
from scripts.app_settings import PROJECTS_DB_PATH
import uuid

logger = logging.getLogger(__name__)

class ProjectRepository:
    """
    Persistence layer for Projects and Project Files using Async SQLModel.
    Isolates all SQL logic from the business logic.
    Returns Pydantic Models (Project, ProjectFile) where applicable.
    """
    
    def __init__(self, db_path: str = PROJECTS_DB_PATH):
        self.db_path = db_path

    async def _get_session(self) -> AsyncSession:
        """
        Creates a new AsyncSession using the DatabaseConnectionManager.
        Note: The caller is responsible for closing the session/transaction context.
        Ideally usage is `async for session in db_manager.get_async_session(): ...`
        but effectively we will use proper async with context managers in methods.
        """
        from scripts.core.db_manager import DatabaseConnectionManager
        # get_async_session is a generator, so we use it as context manager
        session_gen = DatabaseConnectionManager(self.db_path).get_async_session()
        # This returns the generator. We need to iterate it or use `async with` on calling side?
        # Actually `get_async_session` is defined as `async for`.
        # Correct usage: async with async_session() as session.
        # But get_async_session is a Helper Generator.
        # Let's verify `db_manager.py` implementation again.
        # It yields session. 
        # So: 
        async for session in session_gen:
            yield session

    # Helper for cleaner code
    def _session_scope(self):
        from scripts.core.db_manager import DatabaseConnectionManager
        return DatabaseConnectionManager(self.db_path).get_async_session()

    async def add_activity_log(self, project_id: str, activity_type: str, description: str):
        """Records a new activity log entry."""
        # Activity Log table might not be in SQLModel yet? 
        # It was raw SQL in previous version.
        # We should stick to raw SQL via session for tables not in SQLModel OR add it.
        # For now, let's execute raw SQL asynchronously for ActivityLog to avoid changing db_models too much if not planned.
        # But `session.execute` can run text.
        from sqlalchemy import text
        async for session in self._session_scope():
            try:
                await session.execute(
                    text("""
                        INSERT INTO activity_log (log_id, project_id, type, description, timestamp)
                        VALUES (:log_id, :project_id, :type, :description, :timestamp)
                    """),
                    {
                        "log_id": str(uuid.uuid4()),
                        "project_id": project_id,
                        "type": activity_type,
                        "description": description,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                )
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to add activity log: {e}")

    async def get_recent_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves the latest activity logs with project names."""
        from sqlalchemy import text
        async for session in self._session_scope():
            result = await session.execute(
                text("""
                    SELECT l.*, p.name as title
                    FROM activity_log l
                    JOIN projects p ON l.project_id = p.project_id
                    ORDER BY l.timestamp DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.mappings().all()
            return [dict(row) for row in rows]
        return []

    # --- Project CRUD ---

    async def get_project(self, project_id: str) -> Optional[Project]:
        async for session in self._session_scope():
            start_q = select(Project).where(Project.project_id == project_id)
            result = await session.execute(start_q)
            return result.scalar_one_or_none()
        return None

    async def list_projects(self, status: Optional[str] = None) -> List[Project]:
        async for session in self._session_scope():
            query = select(Project)
            if status:
                query = query.where(Project.status == status)
            query = query.order_by(col(Project.last_modified).desc())
            
            result = await session.execute(query)
            return list(result.scalars().all())
        return []

    async def create_project(self, project_data: Project) -> Project:
        async for session in self._session_scope():
            try:
                session.add(project_data)
                await session.commit()
                await session.refresh(project_data)
                return project_data
            except Exception as e:
                await session.rollback()
                raise e

    async def update_project_status(self, project_id: str, status: str):
        async for session in self._session_scope():
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.status = status
                project.last_modified = current_time
                session.add(project)
                await session.commit()

    async def update_project_notes(self, project_id: str, notes: str):
        """Persists project notes to the database and updates last_modified."""
        async for session in self._session_scope():
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.notes = notes
                project.last_modified = current_time
                session.add(project)
                await session.commit()

    async def touch_project(self, project_id: str):
        """Updates the last_modified timestamp for a project."""
        async for session in self._session_scope():
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.last_modified = current_time
                session.add(project)
                await session.commit()

    async def update_project_metadata(self, project_id: str, game_id: str, source_language: str):
        async for session in self._session_scope():
            current_time = datetime.datetime.now().isoformat()
            statement = select(Project).where(Project.project_id == project_id)
            results = await session.execute(statement)
            project = results.scalar_one_or_none()
            if project:
                project.game_id = game_id
                project.source_language = source_language
                project.last_modified = current_time
                session.add(project)
                await session.commit()

    async def delete_project(self, project_id: str):
        async for session in self._session_scope():
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
                
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e

    async def get_project_by_file_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        # This was doing a JOIN and returning project data.
        async for session in self._session_scope():
            query = select(Project).join(ProjectFile).where(ProjectFile.file_id == file_id)
            result = await session.execute(query)
            project = result.scalar_one_or_none()
            return project.model_dump() if project else None

    # --- File Operations (Async Batch) ---

    async def batch_upsert_files(self, project_files: List[Dict[str, Any]]):
        """
        Upserts a batch of files. SQLModel doesn't support generic upsert easily across DBs,
        but since we are SQLite specific with async engine, we can use SQLite ON CONFLICT logic 
        via raw SQL or check-then-update.
        Given performance needs, raw SQL execute is best for batch upsert in SQLite.
        """
        if not project_files:
            return

        from sqlalchemy import text
        
        async for session in self._session_scope():
            try:
                # Construct list of binding params
                # We can't use executemany with async session directly in the same way as sqlite3 cursor?
                # SQLAlchemy 1.4/2.0 async session.execute supports list of params for bulk insert.
                
                stmt = text('''
                    INSERT INTO project_files (file_id, project_id, file_path, status, original_key_count, line_count, file_type)
                    VALUES (:file_id, :project_id, :file_path, :status, :original_key_count, :line_count, :file_type)
                    ON CONFLICT(file_id) DO UPDATE SET
                        status = excluded.status,
                        line_count = excluded.line_count,
                        file_type = excluded.file_type,
                        file_path = excluded.file_path
                ''')
                
                await session.execute(stmt, project_files)
                await session.commit()
            except Exception as e:
                logger.error(f"Batch upsert failed: {e}")
                await session.rollback()
                raise e

    async def delete_files_by_ids(self, file_ids: List[str]):
        if not file_ids: return
        from sqlalchemy import delete
        
        async for session in self._session_scope():
            try:
                stmt = delete(ProjectFile).where(col(ProjectFile.file_id).in_(file_ids))
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e

    async def update_file_status_by_id(self, file_id: str, status: str):
        async for session in self._session_scope():
            stmt = select(ProjectFile).where(ProjectFile.file_id == file_id)
            result = await session.execute(stmt)
            file_record = result.scalar_one_or_none()
            if file_record:
                file_record.status = status
                session.add(file_record)
                await session.commit()

    async def get_project_file_ids(self, project_id: str) -> List[str]:
        async for session in self._session_scope():
            stmt = select(ProjectFile.file_id).where(ProjectFile.project_id == project_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_project_files(self, project_id: str) -> List[ProjectFile]:
        async for session in self._session_scope():
            stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Retrieves aggregate statistics for the dashboard.
        """
        from sqlalchemy import func, text
        
        async for session in self._session_scope():
            # 1. Total Projects
            res = await session.execute(select(func.count(Project.project_id)))
            total_projects = res.scalar_one()
            
            # 2. Active Projects
            res = await session.execute(select(func.count(Project.project_id)).where(Project.status == 'active'))
            active_projects = res.scalar_one()
            
            # 3. File Statistics (by status)
            # Use raw SQL for group by simplicity or construct complex sqlalchemy query
            stmt = text("""
                SELECT status, COUNT(*) as count, SUM(original_key_count) as total_keys
                FROM project_files
                GROUP BY status
            """)
            result = await session.execute(stmt)
            file_stats = result.mappings().all()
            
            status_counts = {row['status']: row['count'] for row in file_stats}
            status_keys = {row['status']: (row['total_keys'] or 0) for row in file_stats}
            
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
