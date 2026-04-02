from typing import Optional, List
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

class EmbeddedWorkshopConfig(BaseModel):
    enabled: bool = True
    follow_primary_settings: bool = True
    api_provider: Optional[str] = None
    api_model: Optional[str] = None
    batch_size_limit: Optional[int] = 10
    concurrency_limit: Optional[int] = 1
    rpm_limit: Optional[int] = 40

class IncrementalUpdateRequest(BaseModel):
    project_id: Optional[str] = None
    target_lang_codes: List[LanguageCode] = [LanguageCode.ZH_CN]
    api_provider: str = "gemini"
    provider: Optional[str] = None # Alias for api_provider (for legacy/frontend compatibility)
    model: str = "gemini-pro"
    concurrency_limit: Optional[int] = None
    rpm_limit: Optional[int] = None
    mod_context: Optional[str] = ""
    dry_run: bool = False
    custom_source_path: Optional[str] = None
    use_resume: bool = True
    embedded_workshop: Optional[EmbeddedWorkshopConfig] = None

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_target_langs(cls, v):
        from scripts.schemas.common import LanguageCode
        if isinstance(v, str):
            if "," in v:
                return [LanguageCode.from_str(code.strip()) for code in v.split(",") if code.strip()]
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v
