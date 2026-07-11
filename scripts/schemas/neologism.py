from typing import List, Optional
from pydantic import BaseModel

class ApproveNeologismRequest(BaseModel):
    project_id: str
    final_translation: str
    glossary_id: Optional[int] = None
    source_lang: Optional[str] = None
    target_lang: Optional[str] = None

class UpdateNeologismRequest(BaseModel):
    project_id: str
    suggestion: str

class MineNeologismsRequest(BaseModel):
    project_id: str
    api_provider: str
    target_lang: str = "zh-CN"
    file_paths: Optional[List[str]] = None

class ProjectGlossaryBindingRequest(BaseModel):
    glossary_id: int
