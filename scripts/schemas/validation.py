from typing import Optional
from pydantic import BaseModel

class ValidationRequest(BaseModel):
    game_id: str
    content: str
    source_lang_code: Optional[str] = "en_US"
    target_lang: Optional[str] = None

class ValidateFileRequest(BaseModel):
    file_path: str
    game_id: str
    target_lang: Optional[str] = None
