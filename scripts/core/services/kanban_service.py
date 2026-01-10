import os
import logging
from typing import List, Dict, Any, Optional
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.strategies.file_linking import FileLinkingStrategy, ParadoxFileLinkingStrategy

logger = logging.getLogger(__name__)

class KanbanService:
    """
    Service to manage Kanban board state and logic.
    Strictly handles data manipulation (JSON Sidecar) and does NOT perform disk scanning.
    """

    def __init__(self, linking_strategy: Optional[FileLinkingStrategy] = None):
        # Default to Paradox strategy if none provided
        self.linking_strategy = linking_strategy or ParadoxFileLinkingStrategy()

    def get_board(self, source_path: str) -> Dict[str, Any]:
        """
        Retrieves the Kanban board data from the project's JSON sidecar.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            return json_manager.get_kanban_data()
        except Exception as e:
            logger.error(f"Failed to get kanban board for {source_path}: {e}")
            raise

    def save_board(self, source_path: str, kanban_data: Dict[str, Any]) -> None:
        """
        Saves the Kanban board data to the project's JSON sidecar.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            json_manager.save_kanban_data(kanban_data)
        except Exception as e:
            logger.error(f"Failed to save kanban board for {source_path}: {e}")
            raise

    def sync_files_to_board(self, source_path: str, files: List[Dict[str, Any]]) -> None:
        """
        Syncs a list of files (provided by an external scanner) to the Kanban board.
        Delegates core linking and task creation logic to the active FileLinkingStrategy.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            kanban_data = json_manager.get_kanban_data()
            tasks = kanban_data.get("tasks", {})
            columns = kanban_data.get("columns", [])
            
            # Robustness: Ensure default columns exist
            default_columns = ["todo", "in_progress", "proofreading", "paused", "done"]
            if len(columns) < 3:
                columns = default_columns
            
            # DELEGATE: Use the strategy to process files and update tasks
            updated_tasks = self.linking_strategy.process_files(source_path, files, tasks)

            # Save Board
            json_manager.save_kanban_data({
                "columns": columns,
                "tasks": updated_tasks,
                "column_order": kanban_data.get("column_order", columns)
            })
            logger.info(f"KanbanService: Synced board for {source_path}. Total tasks: {len(updated_tasks)}")
            
        except Exception as e:
            logger.error(f"Failed to sync files to kanban: {e}")
            raise
