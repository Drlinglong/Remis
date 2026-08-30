from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, Optional, List

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
    reasoning_builtin_enabled: Optional[bool] = None
    reasoning_preset: Optional[str] = None
    custom_parameters: Optional[Dict[str, Any]] = None

class TestProviderConnectionRequest(BaseModel):
    provider_id: str
    api_url: str


class CustomProviderProfileCreateRequest(BaseModel):
    """Write contract for one saved OpenAI-compatible provider profile."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., min_length=1, max_length=120)
    api_url: str = Field(..., min_length=1, max_length=2048)
    models: List[str] = Field(default_factory=list)
    selected_model: str = Field(..., min_length=1, max_length=512)
    prompt_prefix: str = Field(default="", max_length=10000)
    system_prompt_suffix: str = Field(default="", max_length=10000)
    reasoning_builtin_enabled: bool = False
    reasoning_preset: Optional[str] = Field(default=None, max_length=32)
    custom_parameters: Dict[str, Any] = Field(default_factory=dict)
    # Write-only by convention: the router never serializes this model.
    api_key: Optional[str] = Field(default=None, max_length=4096)

class CustomProviderProfileUpdateRequest(BaseModel):
    """Partial write contract for an existing provider profile."""

    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    api_url: Optional[str] = Field(default=None, min_length=1, max_length=2048)
    models: Optional[List[str]] = None
    selected_model: Optional[str] = Field(default=None, min_length=1, max_length=512)
    prompt_prefix: Optional[str] = Field(default=None, max_length=10000)
    system_prompt_suffix: Optional[str] = Field(default=None, max_length=10000)
    reasoning_builtin_enabled: Optional[bool] = None
    reasoning_preset: Optional[str] = Field(default=None, max_length=32)
    custom_parameters: Optional[Dict[str, Any]] = None
    # Empty string explicitly clears the stored secret; omission preserves it.
    api_key: Optional[str] = Field(default=None, max_length=4096)
