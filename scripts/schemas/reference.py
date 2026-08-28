from typing import List, Optional

from pydantic import BaseModel, Field
from scripts.schemas.common import LanguageCode


class ReferenceReuseExclusion(BaseModel):
    file_path: str
    key: str
    source_text: str
    target_lang_code: str


class ReferenceReuseConfig(BaseModel):
    enabled: bool = True
    localization_path: Optional[str] = None
    excluded_entries: List[ReferenceReuseExclusion] = Field(default_factory=list)


class ReferenceReusePreviewRequest(BaseModel):
    project_id: str
    source_lang_code: LanguageCode
    target_lang_codes: List[LanguageCode]
    localization_path: Optional[str] = None
    custom_source_path: Optional[str] = None


class ReferenceLibraryBuildRequest(BaseModel):
    game_id: str
    localization_path: str


class ReferenceLibraryOperation(BaseModel):
    game_id: str
    localization_path: str
    action: str = "build"


class ReferenceLibraryJobRequest(BaseModel):
    operations: List[ReferenceLibraryOperation] = Field(default_factory=list)
