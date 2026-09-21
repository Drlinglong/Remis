from typing import Optional
from pydantic import BaseModel

class WorkshopRequest(BaseModel):
    item_id: str
    user_template: str
    target_language: str
    project_id: Optional[str] = ""
    custom_language: Optional[str] = ""
    api_provider: str


class WorkshopDescriptionResponse(BaseModel):
    bbcode: str
    saved_path: str
