from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from scripts.schemas.common import LanguageCode


class AgentJobPlanRequest(BaseModel):
    project_id: str
    target_lang_codes: List[LanguageCode] = Field(
        default_factory=lambda: [LanguageCode.ZH_CN]
    )
    api_provider: str = "lm_studio"
    model: str = "local-model"
    batch_size_limit: Optional[int] = None
    concurrency_limit: Optional[int] = 1
    rpm_limit: Optional[int] = 40
    use_resume: bool = True
    use_main_glossary: bool = True
    embedded_workshop_enabled: bool = True
    dry_run: bool = False

    @field_validator("target_lang_codes", mode="before")
    @classmethod
    def normalize_target_languages(cls, value):
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [
                LanguageCode.from_str(item) if isinstance(item, str) else item
                for item in value
            ]
        return value


class AgentJobStartRequest(BaseModel):
    plan_id: str
    approved: bool = False


class AgentProjectInspectRequest(BaseModel):
    folder_path: str


class AgentProjectPlanRequest(BaseModel):
    name: str
    folder_path: str
    game_id: str
    source_language: LanguageCode = LanguageCode.EN
    import_mode: Literal["copy", "reference"] = "copy"

    @field_validator("source_language", mode="before")
    @classmethod
    def normalize_source_language(cls, value):
        if isinstance(value, str):
            return LanguageCode.from_str(value)
        return value


class AgentProjectCreateRequest(BaseModel):
    plan_id: str
    approved: bool = False


class AgentRepairRequest(BaseModel):
    approved: bool = False
    api_provider: Optional[str] = None
    api_model: Optional[str] = None
    batch_size_limit: Optional[int] = None
    concurrency_limit: Optional[int] = 1
    rpm_limit: Optional[int] = 40
    max_retries: Optional[int] = 3


class AgentExportRequest(BaseModel):
    approved: bool = False
    confirm_overwrite: bool = False
    output_folder_name: Optional[str] = None
    game_id: Optional[str] = None
    target_deploy_path: Optional[str] = None


class AgentProgress(BaseModel):
    completed_files: int = 0
    total_files: int = 0
    percent: int = 0
    current_file: str = ""
    stage: str = ""
    successful_batches: int = 0
    failed_batches: int = 0


class AgentValidationSummary(BaseModel):
    errors: int = 0
    warnings: int = 0
    human_review_items: int = 0
    total: int = 0
    available: bool = False
    truncated: bool = False


class AgentJobResponse(BaseModel):
    job_id: str
    project_id: Optional[str] = None
    status: Literal[
        "queued",
        "running",
        "awaiting_approval",
        "completed",
        "failed",
        "cancelled",
        "interrupted",
        "unknown",
    ]
    kind: str = "translation"
    progress: AgentProgress = Field(default_factory=AgentProgress)
    validation: AgentValidationSummary = Field(
        default_factory=AgentValidationSummary
    )
    allowed_actions: List[str] = Field(default_factory=list)
    output_paths: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    recovery: Dict[str, Any] = Field(default_factory=dict)
    links: Dict[str, str] = Field(default_factory=dict)


class AgentPlanResponse(BaseModel):
    plan_id: str
    status: Literal["awaiting_approval", "ready"]
    project_id: str
    dry_run: bool = False
    requires_approval: bool = True
    risk: Dict[str, Any] = Field(default_factory=dict)
    summary: str
    allowed_actions: List[str] = Field(default_factory=list)
    expires_at: str


class AgentProjectPlanResponse(BaseModel):
    plan_id: str
    status: Literal["awaiting_approval"]
    requires_approval: bool = True
    inspection: Dict[str, Any] = Field(default_factory=dict)
    risk: Dict[str, Any] = Field(default_factory=dict)
    summary: str
    allowed_actions: List[str] = Field(default_factory=list)
    expires_at: str


class AgentProjectSummary(BaseModel):
    project_id: str
    name: str
    game_id: str
    source_language: str
    status: str
    file_count: int = 0
    file_status_counts: Dict[str, int] = Field(default_factory=dict)
    validation: AgentValidationSummary = Field(
        default_factory=AgentValidationSummary
    )
    allowed_actions: List[str] = Field(default_factory=list)
