from typing import Dict, List, Literal, Optional
from pydantic import AliasChoices, BaseModel, Field, model_validator

class GlossaryEntryIn(BaseModel):
    id: str
    source: str
    translations: Dict[str, str]
    notes: Optional[str] = ""
    variants: Optional[Dict[str, List[str]]] = {}
    abbreviations: Optional[Dict[str, str]] = {}
    metadata: Optional[Dict] = {}

class SearchGlossaryRequest(BaseModel):
    scope: str = Field(..., description="Search scope: 'file', 'game', or 'all'")
    query: str = Field(..., description="Search query string")
    game_id: Optional[str] = None
    file_name: Optional[str] = None
    page: int = 1
    pageSize: int = 25

class CreateGlossaryRequest(BaseModel):
    game_id: str
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        validation_alias=AliasChoices("name", "file_name"),
    )

class DuplicateGlossaryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)

class UpdateGlossaryMetadataRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    kind: Optional[Literal["main", "project", "standard"]] = None
    project_ids: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_kind_and_bindings(self):
        project_ids = list(dict.fromkeys(
            project_id.strip()
            for project_id in (self.project_ids or [])
            if project_id and project_id.strip()
        ))
        self.project_ids = project_ids if self.project_ids is not None else None
        if self.kind == "project" and not project_ids:
            raise ValueError("A project glossary must be bound to at least one project.")
        if self.kind in {"main", "standard"} and project_ids:
            raise ValueError("Main and standard glossaries cannot have project bindings.")
        return self

class GlossaryBatchSelectionRequest(BaseModel):
    glossary_ids: List[int] = Field(..., min_length=1, max_length=100)

class BatchDeleteGlossariesRequest(GlossaryBatchSelectionRequest):
    confirm_main_glossaries: bool = False
    confirm_project_bindings: bool = False


class GlossaryMergeRequest(GlossaryBatchSelectionRequest):
    target_mode: Literal["new", "existing"] = "new"
    target_glossary_id: Optional[int] = None
    target_name: Optional[str] = Field(default=None, max_length=200)
    conflict_strategy: Literal[
        "keep_first",
        "keep_last",
        "keep_target",
        "skip_conflicts",
    ] = "skip_conflicts"

    @model_validator(mode="after")
    def validate_target(self):
        if len(set(self.glossary_ids)) < 2:
            raise ValueError("Select at least two glossaries to merge.")
        if self.target_mode == "new" and not (self.target_name or "").strip():
            raise ValueError("A name is required for a new merged glossary.")
        if self.target_mode == "existing" and self.target_glossary_id is None:
            raise ValueError("Select an existing target glossary.")
        if self.target_mode == "new" and self.conflict_strategy == "keep_target":
            raise ValueError("keep_target is only available for an existing target glossary.")
        return self


class GlossaryHealthCheckRequest(GlossaryBatchSelectionRequest):
    target_lang: Optional[str] = None
    include_ai_advice: bool = False
    confirm_model_usage: bool = False
    api_provider: Optional[str] = None
    model_name: Optional[str] = None
    concurrency_limit: int = Field(default=1, ge=1, le=6)

    @model_validator(mode="after")
    def validate_ai_request(self):
        if self.include_ai_advice:
            if not self.confirm_model_usage:
                raise ValueError("AI advice requires explicit model-usage confirmation.")
            if not (self.api_provider or "").strip():
                raise ValueError("Select a provider for AI advice.")
            if not (self.model_name or "").strip():
                raise ValueError("Select a model for AI advice.")
            if not (self.target_lang or "").strip():
                raise ValueError("Select a target language for AI translation suggestions.")
        return self

class GlossaryEntryCreate(BaseModel):
    source: str
    translations: Dict[str, str]
    notes: Optional[str] = ""
    variants: Optional[Dict[str, List[str]]] = {}
    abbreviations: Optional[Dict[str, str]] = {}
    metadata: Optional[Dict] = {}
