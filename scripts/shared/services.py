import os
import sqlite3
import sys
from scripts import app_settings
from scripts.core.services.kanban_service import KanbanService
from scripts.core.services.file_service import FileService
from scripts.core.services.proofreading_service import ProofreadingService
from scripts.core.glossary_manager import glossary_manager
from scripts.core.project_manager import ProjectManager
from scripts.core.archive_manager import ArchiveManager
from scripts.core.repositories.project_repository import ProjectRepository
from scripts.core.repositories.project_watch_repository import ProjectWatchRepository
from scripts.core.repositories.model_arena_repository import ModelArenaRepository
from scripts.core.services.model_arena_service import ModelArenaService
from scripts.core.services.project_watch_service import ProjectWatchService

# Initialize Managers/Services
# Order matters for dependency injection

# 1. Base Services / Managers / Repositories
project_repository = ProjectRepository()
project_watch_repository = ProjectWatchRepository()
# glossary_manager imported from scripts.core.glossary_manager
archive_manager = ArchiveManager()
kanban_service = KanbanService()

# 2. Orchestrator Services
file_service = FileService()

# 3. High-Level Facades
# ProjectManager needs file_service injected, AND project_repository
project_manager = ProjectManager(
    file_service=file_service,
    project_repository=project_repository,
    kanban_service=kanban_service
)

project_watch_service = ProjectWatchService(
    watch_repository=project_watch_repository,
    project_repository=project_repository,
)

model_arena_repository = ModelArenaRepository(app_settings.REMIS_DB_PATH)
model_arena_service = ModelArenaService(
    repository=model_arena_repository,
    project_manager=project_manager,
    glossary_manager=glossary_manager,
)

proofreading_service = ProofreadingService(
    project_manager=project_manager,
    archive_manager=archive_manager
)
