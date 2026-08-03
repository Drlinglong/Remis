from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

class ApproveNeologismRequest(BaseModel):
    project_id: str
    resolution: Literal["approve_project", "duplicate", "new_meaning"] = "approve_project"
    final_translation: str = ""
    glossary_id: Optional[int] = None
    source_lang: Optional[str] = None
    target_lang: Optional[str] = None

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("project_id is required")
        return value

    @model_validator(mode="after")
    def validate_translation(self):
        self.final_translation = self.final_translation.strip()
        if self.resolution != "duplicate" and not self.final_translation:
            raise ValueError("final_translation is required unless the candidate is marked duplicate")
        return self

class UpdateNeologismRequest(BaseModel):
    project_id: str
    suggestion: str = Field(min_length=1)

class MineNeologismsRequest(BaseModel):
    project_id: str = Field(min_length=1)
    api_provider: str = Field(min_length=1)
    model_name: Optional[str] = None
    target_lang: str = Field(default="zh-CN", min_length=1)
    review_language: str = Field(
        default="en",
        min_length=2,
        max_length=16,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$",
    )
    description_language: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=16,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$",
    )
    file_paths: Optional[List[str]] = None
    analysis_scope: Literal["terms_only", "narrative_context"] = "terms_only"
    upstream_version: Optional[str] = Field(default=None, max_length=200)
    concurrency_limit: Optional[int] = Field(default=None, ge=1, le=50)

    @property
    def effective_description_language(self) -> str:
        return self.description_language or self.review_language

class RestoreNeologismRequest(BaseModel):
    project_id: str = Field(min_length=1)

class ProjectGlossaryBindingRequest(BaseModel):
    glossary_id: int
