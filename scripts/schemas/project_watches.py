from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CreateProjectWatchRequest(BaseModel):
    name: str
    path: str
    project_id: Optional[str] = None
    enabled: bool = True
    scan_interval_minutes: Optional[int] = Field(default=None, ge=1)


class UpdateProjectWatchRequest(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    project_id: Optional[str] = None
    enabled: Optional[bool] = None
    scan_interval_minutes: Optional[int] = Field(default=None, ge=1)


class ScanProjectWatchesRequest(BaseModel):
    watch_ids: List[str]


class ProjectWatchScanSummary(BaseModel):
    watch_id: str
    status: str
    baseline_created: bool
    root_path: Optional[str] = None
    scanned_file_count: int
    added_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0
    changed_count: int = 0
    added: List[Dict[str, Any]]
    modified: List[Dict[str, Any]]
    deleted: List[Dict[str, Any]]
