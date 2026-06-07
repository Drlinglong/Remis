from pydantic import BaseModel
from typing import Optional, List

class UpdateConfigRequest(BaseModel):
    action: Optional[str] = None
    path: Optional[str] = None
    source_path: Optional[str] = None
    translation_dirs: Optional[List[str]] = None

class UpdateApiKeyRequest(BaseModel):
    provider_id: str
    api_key: str

class UpdateProviderConfigRequest(BaseModel):
    provider_id: str
    api_key: Optional[str] = None
    models: Optional[List[str]] = None # Custom models list
    api_url: Optional[str] = None # Custom API URL
    selected_model: Optional[str] = None # Currently selected model
    prompt_prefix: Optional[str] = None # Optional text prepended to user prompts, e.g. /no_think
    system_prompt_suffix: Optional[str] = None # Optional text appended to provider system prompts
