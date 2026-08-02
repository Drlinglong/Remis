from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, field_validator
from scripts.schemas.common import LanguageCode

class CreateProjectRequest(BaseModel):
    name: str
    folder_path: str
    game_id: str
    source_language: LanguageCode = LanguageCode.EN
    import_mode: str = "copy"

    @field_validator('source_language', mode='before')
    @classmethod
    def normalize_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v

class UpdateProjectStatusRequest(BaseModel):
    status: Literal["active", "archived", "deleted"]

class UpdateProjectNotesRequest(BaseModel):
    notes: str

class UpdateFileStatusRequest(BaseModel):
    status: Literal["todo", "in_progress", "proofreading", "paused", "done"]

    @field_validator('status', mode='before')
    @classmethod
    def normalize_legacy_file_status(cls, v):
        if v == "translated":
            return "done"
        return v

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
    status: Literal["todo", "in_progress", "proofreading", "paused", "done"]
    original_key_count: int
    line_count: int
    file_type: str 


class ProjectSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_id: str
    name: str
    status: Literal["active", "archived", "deleted"]
    game_id: Optional[str] = None
    source_path: Optional[str] = None
    source_language: Optional[str] = None


class ActionResponse(BaseModel):
    status: Literal["success"]
    message: Optional[str] = None


class ProjectLifecycleResult(BaseModel):
    project_id: str
    previous_status: Literal["active", "archived", "deleted"]
    status: Literal["active", "archived", "deleted"]
    paused_watch_count: int = 0
    restored_watch_count: int = 0


class ProjectStatusActionResponse(ActionResponse):
    lifecycle: ProjectLifecycleResult


class FileDiscoveryWarning(BaseModel):
    code: Literal[
        "directory_unavailable",
        "directory_scan_failed",
        "file_read_failed",
        "invalid_file_status",
    ]
    file_type: Literal["source", "translation"]
    path: str


class FileDiscoveryResponse(BaseModel):
    status: Literal["success"]
    project_id: str
    files: List[ProjectFile]
    file_count: int
    scanned_paths: List[str]
    warnings: List[FileDiscoveryWarning]


class TranslationUploadResponse(BaseModel):
    status: Literal["success", "warning", "info"]
    message: str
    match_count: Optional[int] = None
    version_id: Optional[int] = None

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
    model: str = "gemini-3.6-flash"
    batch_size_limit: Optional[int] = None
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
