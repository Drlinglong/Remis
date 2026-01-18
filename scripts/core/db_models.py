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
    is_main: bool = Field(default=False)

class GlossaryEntry(SQLModel, table=True):
    __tablename__ = "entries"
    
    entry_id: str = Field(primary_key=True)
    glossary_id: int = Field(foreign_key="glossaries.glossary_id", index=True)
    
    # Use SQLAlchemy JSON column type to handle serialization automatically
    translations: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    abbreviations: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    variants: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    raw_metadata: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

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
