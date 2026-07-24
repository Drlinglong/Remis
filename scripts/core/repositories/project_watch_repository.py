import datetime
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, text
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from scripts.app_settings import PROJECTS_DB_PATH, relativize_path, resolve_path
from scripts.core.db_models import ProjectWatch, ProjectWatchFileSnapshot


class ProjectWatchRepository:
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

    def _resolve_watch(self, watch: ProjectWatch) -> ProjectWatch:
        return watch.model_copy(update={"path": resolve_path(watch.path)})

    async def list_watches(self, session: Optional[AsyncSession] = None) -> List[ProjectWatch]:
        async with self._use_session(session) as session:
            result = await session.execute(select(ProjectWatch).order_by(col(ProjectWatch.name).asc()))
            return [self._resolve_watch(watch) for watch in result.scalars().all()]

    async def get_watch(self, watch_id: str, session: Optional[AsyncSession] = None) -> Optional[ProjectWatch]:
        async with self._use_session(session) as session:
            result = await session.execute(select(ProjectWatch).where(ProjectWatch.watch_id == watch_id))
            watch = result.scalar_one_or_none()
            return self._resolve_watch(watch) if watch else None

    async def create_watch(self, data: Dict[str, Any], session: Optional[AsyncSession] = None) -> ProjectWatch:
        async with self._use_session(session) as session:
            try:
                watch = ProjectWatch(
                    watch_id=data.get("watch_id") or str(uuid.uuid4()),
                    name=data["name"],
                    path=relativize_path(data["path"]),
                    project_id=data.get("project_id") or None,
                    enabled=bool(data.get("enabled", True)),
                    paused_by_project_archive=False,
                    scan_interval_minutes=data.get("scan_interval_minutes"),
                    status="never_scanned",
                    last_scan_summary={},
                )
                session.add(watch)
                await self._commit_if_owner(session)
                if self._owns_session(session):
                    await session.refresh(watch)
                return self._resolve_watch(watch)
            except Exception:
                await self._rollback_if_owner(session)
                raise

    async def update_watch(self, watch_id: str, data: Dict[str, Any], session: Optional[AsyncSession] = None) -> Optional[ProjectWatch]:
        async with self._use_session(session) as session:
            try:
                result = await session.execute(select(ProjectWatch).where(ProjectWatch.watch_id == watch_id))
                watch = result.scalar_one_or_none()
                if not watch:
                    return None
                for key in ["name", "project_id", "enabled", "scan_interval_minutes"]:
                    if key in data:
                        setattr(watch, key, data[key])
                if "enabled" in data:
                    watch.paused_by_project_archive = False
                if "path" in data:
                    watch.path = relativize_path(data["path"])
                session.add(watch)
                await self._commit_if_owner(session)
                if self._owns_session(session):
                    await session.refresh(watch)
                return self._resolve_watch(watch)
            except Exception:
                await self._rollback_if_owner(session)
                raise

    async def delete_watch(self, watch_id: str, session: Optional[AsyncSession] = None) -> None:
        async with self._use_session(session) as session:
            try:
                await session.execute(delete(ProjectWatchFileSnapshot).where(ProjectWatchFileSnapshot.watch_id == watch_id))
                await session.execute(delete(ProjectWatch).where(ProjectWatch.watch_id == watch_id))
                await self._commit_if_owner(session)
            except Exception:
                await self._rollback_if_owner(session)
                raise

    async def get_snapshots(self, watch_id: str, session: Optional[AsyncSession] = None) -> List[ProjectWatchFileSnapshot]:
        async with self._use_session(session) as session:
            result = await session.execute(
                select(ProjectWatchFileSnapshot).where(ProjectWatchFileSnapshot.watch_id == watch_id)
            )
            return list(result.scalars().all())

    async def replace_snapshots_and_update_watch(
        self,
        watch_id: str,
        snapshots: List[Dict[str, Any]],
        summary: Dict[str, Any],
        status: str,
        changed: bool,
        session: Optional[AsyncSession] = None,
    ) -> None:
        async with self._use_session(session) as session:
            try:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                await session.execute(delete(ProjectWatchFileSnapshot).where(ProjectWatchFileSnapshot.watch_id == watch_id))
                for item in snapshots:
                    session.add(ProjectWatchFileSnapshot(
                        snapshot_id=str(uuid.uuid4()),
                        watch_id=watch_id,
                        relative_path=item["relative_path"],
                        sha256=item["sha256"],
                        size=item["size"],
                        mtime_ns=item["mtime_ns"],
                        last_seen_at=now,
                    ))

                result = await session.execute(select(ProjectWatch).where(ProjectWatch.watch_id == watch_id))
                watch = result.scalar_one_or_none()
                if watch:
                    watch.last_scan_at = now
                    if changed:
                        watch.last_change_at = now
                    watch.status = status
                    watch.last_scan_summary = summary
                    session.add(watch)
                await self._commit_if_owner(session)
            except Exception:
                await self._rollback_if_owner(session)
                raise
