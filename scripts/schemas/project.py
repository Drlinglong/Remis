from typing import Optional
from pydantic import BaseModel, field_validator
from scripts.schemas.common import LanguageCode

class CreateProjectRequest(BaseModel):
    name: str
    folder_path: str
    game_id: str
    source_language: LanguageCode = LanguageCode.EN

    @field_validator('source_language', mode='before')
    @classmethod
    def normalize_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v

class UpdateProjectStatusRequest(BaseModel):
    status: str

class UpdateProjectNotesRequest(BaseModel):
    notes: str

class UpdateFileStatusRequest(BaseModel):
    status: str

class UpdateProjectMetadataRequest(BaseModel):
    game_id: str
    source_language: LanguageCode

    @field_validator('source_language', mode='before')
    @classmethod
    def normalize_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v

class Project(BaseModel):
    project_id: str
    name: str
    game_id: str
    source_path: str
    source_language: str
    status: str
    created_at: str
    last_modified: str

class ProjectFile(BaseModel):
    file_id: str
    project_id: str
    file_path: str
    status: str 
    original_key_count: int
    line_count: int
    file_type: str 
