from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from scripts.schemas.common import LanguageCode


class TranslationTaskResponse(BaseModel):
    task_id: str
    message: str
    status: Optional[str] = None


class SourceModResponse(BaseModel):
    name: str
    path: str
    mtime: float


class CheckpointTargetResponse(BaseModel):
    target_lang_code: str
    exists: bool = False
    completed_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    last_saved_at: Optional[str] = None
    last_completed_file: Optional[str] = None


class CheckpointStatusResponse(BaseModel):
    exists: bool = False
    completed_count: int = 0
    total_files_estimate: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    targets: List[CheckpointTargetResponse] = Field(default_factory=list)


class CheckpointDeleteResponse(BaseModel):
    status: str
    message: str


class CheckpointStatusRequest(BaseModel):
    mod_name: str
    target_lang_codes: List[LanguageCode]

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_langs(cls, v):
        if isinstance(v, str):
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v


class CustomLangConfig(BaseModel):
    name: str
    code: str
    key: str
    folder_prefix: str


class EmbeddedWorkshopConfig(BaseModel):
    enabled: bool = True
    follow_primary_settings: bool = True
    api_provider: Optional[str] = None
    api_model: Optional[str] = None
    batch_size_limit: Optional[int] = 10
    concurrency_limit: Optional[int] = 1
    rpm_limit: Optional[int] = 40


class InitialTranslationRequest(BaseModel):
    project_id: str
    idempotency_key: Optional[str] = None
    source_lang_code: LanguageCode
    target_lang_codes: List[LanguageCode] = [LanguageCode.ZH_CN]
    api_provider: str = "gemini"
    model: str = "gemini-3.6-flash"
    batch_size_limit: Optional[int] = None
    source_context_overlap: int = Field(default=0, ge=0, le=100)
    translation_context_mode: Optional[Literal["none", "glossaries", "archive"]] = None
    use_project_context: bool = True
    context_release_id: Optional[str] = None
    context_character_budget: int = Field(default=4000, ge=0, le=20000)
    concurrency_limit: Optional[int] = None
    rpm_limit: Optional[int] = 40
    mod_context: Optional[str] = ""
    selected_glossary_ids: Optional[List[int]] = []
    use_main_glossary: bool = True
    clean_source: bool = False
    use_resume: bool = True
    custom_lang_config: Optional[CustomLangConfig] = None
    embedded_workshop: Optional[EmbeddedWorkshopConfig] = None

    @field_validator('source_lang_code', mode='before')
    @classmethod
    def normalize_source_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_target_langs(cls, v):
        if isinstance(v, str):
            if "," in v:
                return [LanguageCode.from_str(code.strip()) for code in v.split(",") if code.strip()]
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v


class TranslationRequestV2(BaseModel):
    project_path: str
    game_profile_id: str
    source_lang_code: LanguageCode
    target_lang_codes: List[LanguageCode]
    api_provider: str
    mod_context: Optional[str] = ""
    selected_glossary_ids: Optional[List[int]] = []
    model_name: Optional[str] = None
    use_main_glossary: bool = True
    clean_source: bool = False
    is_existing_source: bool = False
    use_resume: bool = True
    custom_lang_config: Optional[CustomLangConfig] = None
    embedded_workshop: Optional[EmbeddedWorkshopConfig] = None

    @field_validator('source_lang_code', mode='before')
    @classmethod
    def normalize_source_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_target_langs(cls, v):
        if isinstance(v, str):
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v


class IncrementalUpdateConfig(BaseModel):
    project_id: str
    target_lang_codes: List[LanguageCode] = [LanguageCode.ZH_CN]
    api_provider: str = "gemini"
    model: str = "gemini-3.6-flash"
    mod_context: Optional[str] = ""
    source_context_overlap: int = Field(default=0, ge=0, le=100)
    use_project_context: bool = True
    translation_context_mode: Optional[Literal["none", "glossaries", "archive"]] = None
    context_release_id: Optional[str] = None
    context_character_budget: int = Field(default=4000, ge=0, le=20000)
    dry_run: bool = False
    custom_source_path: Optional[str] = None
    use_resume: bool = True

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_target_langs(cls, v):
        if isinstance(v, str):
            if "," in v:
                return [LanguageCode.from_str(code.strip()) for code in v.split(",") if code.strip()]
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v
