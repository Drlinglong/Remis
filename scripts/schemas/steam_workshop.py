from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AssetType = Literal["cover", "description"]
AssetSource = Literal["manual", "model", "generated", "imported"]


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    game_id: str | None = Field(default=None, max_length=80)
    project_id: str | None = Field(default=None, max_length=160)
    workshop_item_id: str | None = Field(default=None, max_length=160)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Workspace name cannot be blank")
        return value


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    game_id: str | None = Field(default=None, max_length=80)
    project_id: str | None = Field(default=None, max_length=160)
    workshop_item_id: str | None = Field(default=None, max_length=160)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Workspace name cannot be blank")
        return value


class CreateDescriptionVersionRequest(BaseModel):
    bbcode: str = Field(min_length=1, max_length=1_000_000)
    language: str = Field(min_length=1, max_length=40)
    source: AssetSource = "manual"
    parent_version_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_description: str | None = Field(default=None, max_length=1_000_000)
    source_description_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )


class CreateCoverVersionRequest(BaseModel):
    png_base64: str = Field(min_length=1)
    canvas: dict[str, Any]
    source: AssetSource = "manual"
    parent_version_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelectVersionRequest(BaseModel):
    version_id: str = Field(min_length=1, max_length=160)


class GenerateDescriptionRequest(BaseModel):
    workshop_item_id: str | None = Field(
        default=None,
        pattern=r"^[0-9]+$",
        max_length=32,
    )
    user_template: str = Field(default="", max_length=100_000)
    target_language_name: str = Field(min_length=1, max_length=80)
    language: str = Field(min_length=1, max_length=40)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    approved: bool = False
