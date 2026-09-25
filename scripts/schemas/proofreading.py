from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from scripts.schemas.common import LanguageCode

class ProofreadingEntry(BaseModel):
    key: str
    translation: str


class StructurePatch(BaseModel):
    entry_id: str
    line_start: int
    line_end: int
    content: str = ""


class SaveProofreadingRequest(BaseModel):
    project_id: str
    file_id: str
    entries: List[ProofreadingEntry]
    structure_patches: List[StructurePatch] = Field(default_factory=list)
    base_revision: Optional[str] = None
    content: str = ""  # Legacy support
    target_language: LanguageCode = LanguageCode.ZH_CN

    @field_validator('target_language', mode='before')
    @classmethod
    def normalize_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v


class AgentSaveProofreadingRequest(SaveProofreadingRequest):
    """Agent saves require explicit approval and optimistic concurrency data."""

    approved: Literal[True]
    base_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_nonblank_revision(self):
        if not self.base_revision.strip():
            raise ValueError("base_revision must not be blank")
        return self
