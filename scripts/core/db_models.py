from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON

class Glossary(SQLModel, table=True):
    __tablename__ = "glossaries"
    
    glossary_id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(index=True)
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    is_main: bool = Field(default=False)
    sources: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class GlossaryEntry(SQLModel, table=True):
    __tablename__ = "entries"
    
    entry_id: str = Field(primary_key=True)
    glossary_id: int = Field(foreign_key="glossaries.glossary_id", index=True)
    
    # Use SQLAlchemy JSON column type to handle serialization automatically
    translations: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    abbreviations: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    variants: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class ProjectGlossaryBinding(SQLModel, table=True):
    __tablename__ = "project_glossary_bindings"

    project_id: str = Field(foreign_key="projects.project_id", primary_key=True)
    glossary_id: int = Field(foreign_key="glossaries.glossary_id", primary_key=True)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class Project(SQLModel, table=True):
    __tablename__ = "projects"

    project_id: str = Field(primary_key=True)
    name: str
    game_id: str = Field(index=True)
    source_path: str
    target_path: Optional[str] = None
    source_language: str
    status: str = Field(default="active", index=True) # active, archived, deleted
    created_at: Optional[str] = None
    last_modified: Optional[str] = None
    last_activity_type: Optional[str] = None
    last_activity_desc: Optional[str] = None
    notes: Optional[str] = None

class ProjectFile(SQLModel, table=True):
    __tablename__ = "project_files"

    file_id: str = Field(primary_key=True)
    project_id: str = Field(foreign_key="projects.project_id", index=True)
    file_path: str
    status: str = Field(default="todo") # todo, extracting, translating, proofreading, done
    original_key_count: int = 0
    line_count: int = 0
    file_type: str = Field(default="source") # source, translation

class ProjectHistory(SQLModel, table=True):
    __tablename__ = "project_history"
    __table_args__ = {"extend_existing": True}

    history_id: str = Field(primary_key=True)
    project_id: str = Field(foreign_key="projects.project_id", index=True)
    timestamp: str
    action_type: str  # import, translate, edit, restore
    description: Optional[str] = None
    snapshot_id: Optional[int] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class ProjectWatch(SQLModel, table=True):
    __tablename__ = "project_watches"

    watch_id: str = Field(primary_key=True)
    name: str
    path: str
    project_id: Optional[str] = Field(default=None, foreign_key="projects.project_id", index=True)
    enabled: bool = Field(default=True)
    scan_interval_minutes: Optional[int] = None
    last_scan_at: Optional[str] = None
    last_change_at: Optional[str] = None
    status: str = Field(default="never_scanned", index=True)
    last_scan_summary: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

class ProjectWatchFileSnapshot(SQLModel, table=True):
    __tablename__ = "project_watch_file_snapshots"

    snapshot_id: str = Field(primary_key=True)
    watch_id: str = Field(foreign_key="project_watches.watch_id", index=True)
    relative_path: str
    sha256: str
    size: int
    mtime_ns: int
    last_seen_at: str

class ActivityLog(SQLModel, table=True):
    __tablename__ = "activity_log"

    log_id: str = Field(primary_key=True)
    project_id: str = Field(foreign_key="projects.project_id", index=True)
    type: str
    description: str
    timestamp: str
