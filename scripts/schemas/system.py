from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SystemStats(BaseModel):
    total_projects: int = 0
    words_translated: int = 0
    active_tasks: int = 0
    active_projects: int = 0
    completion_rate: float = 0.0


class SystemCharts(BaseModel):
    project_status: List[Dict[str, Any]] = Field(default_factory=list)
    glossary_analysis: List[Dict[str, Any]] = Field(default_factory=list)
    project_distribution: List[Dict[str, Any]] = Field(default_factory=list)


class SystemActivity(BaseModel):
    id: Any
    project_id: Optional[str] = None
    type: str
    title: str
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None
    user: str = "System"


class SystemStatsResponse(BaseModel):
    stats: SystemStats
    charts: SystemCharts
    recent_activity: List[SystemActivity] = Field(default_factory=list)


class SystemActionResponse(BaseModel):
    status: str
    message: Optional[str] = None


class DemoResetResponse(SystemActionResponse):
    backup_root: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    moved_path_count: int = 0
    archived_task_count: int = 0


class DatabaseFolderResponse(SystemActionResponse):
    database_file: str
