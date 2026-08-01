from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import CheckConstraint, Column, JSON, UniqueConstraint

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
    paused_by_project_archive: bool = Field(default=False)
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


class SteamWorkshopWorkspace(SQLModel, table=True):
    __tablename__ = "steam_workshop_workspaces"

    workspace_id: str = Field(primary_key=True)
    name: str
    game_id: Optional[str] = Field(default=None, index=True)
    project_id: Optional[str] = Field(
        default=None,
        foreign_key="projects.project_id",
        index=True,
    )
    workshop_item_id: Optional[str] = Field(default=None, index=True)
    current_cover_version_id: Optional[str] = None
    current_description_version_id: Optional[str] = None
    created_at: str
    updated_at: str


class SteamWorkshopAssetVersion(SQLModel, table=True):
    __tablename__ = "steam_workshop_asset_versions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "asset_type",
            "sequence",
            name="ux_steam_workshop_version_sequence",
        ),
        CheckConstraint(
            "asset_type IN ('cover', 'description')",
            name="ck_steam_workshop_asset_type",
        ),
        CheckConstraint(
            "status IN ('candidate', 'selected')",
            name="ck_steam_workshop_asset_status",
        ),
    )

    version_id: str = Field(primary_key=True)
    workspace_id: str = Field(
        foreign_key="steam_workshop_workspaces.workspace_id",
        index=True,
    )
    sequence: int
    asset_type: str = Field(index=True)
    status: str = Field(default="candidate", index=True)
    parent_version_id: Optional[str] = None
    sha256: str
    metadata_json: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )
    source: str
    created_at: str
    description_bbcode: Optional[str] = None
    description_language: Optional[str] = None
    source_description: Optional[str] = None
    source_description_sha256: Optional[str] = None
    cover_file_ref: Optional[str] = None
    cover_mime_type: Optional[str] = None
    cover_width: Optional[int] = None
    cover_height: Optional[int] = None
    cover_canvas_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
