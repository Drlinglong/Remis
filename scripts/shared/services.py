import os
import sqlite3
import sys
from scripts import app_settings
from scripts.core.services.kanban_service import KanbanService
from scripts.core.services.file_service import FileService
from scripts.core.glossary_manager import glossary_manager
from scripts.core.project_manager import ProjectManager
from scripts.core.archive_manager import ArchiveManager
from scripts.core.repositories.project_repository import ProjectRepository

# Initialize Managers/Services
# Order matters for dependency injection

# 1. Base Services / Managers / Repositories
project_repository = ProjectRepository()
# glossary_manager imported from scripts.core.glossary_manager
archive_manager = ArchiveManager()
kanban_service = KanbanService()

# 2. Orchestrator Services
file_service = FileService(
    kanban_service=kanban_service, 
    archive_manager=archive_manager,
    project_repository=project_repository
)

# 3. High-Level Facades
# ProjectManager needs file_service injected, AND project_repository
project_manager = ProjectManager(
    file_service=file_service,
    project_repository=project_repository,
    kanban_service=kanban_service
)
