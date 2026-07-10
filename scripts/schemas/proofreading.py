from typing import List
from pydantic import BaseModel, Field, field_validator
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
    content: str = ""  # Legacy support
    target_language: LanguageCode = LanguageCode.ZH_CN

    @field_validator('target_language', mode='before')
    @classmethod
    def normalize_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v
