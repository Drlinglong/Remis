"""GUI publication contracts; credentials and arbitrary source paths are excluded."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class PublicationPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_folder_name: str = Field(min_length=1, max_length=255)
    app_id: int = Field(gt=0, le=4294967295)
    mode: Literal["create", "update"] = "create"
    published_file_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]{0,19}$")
    title: str = Field(min_length=1, max_length=128)
    change_note: str = Field(default="", max_length=8000)
    visibility: Literal["private", "public", "friends_only", "unlisted"] = "private"
    language: str = Field(default="english", pattern=r"^[a-z_]{2,32}$")
    tags: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("output_folder_name")
    @classmethod
    def folder_name(cls, value):
        if value in {".", ".."} or any(char in value for char in "/\\\x00"):
            raise ValueError("Select one project-owned output folder")
        return value

    @field_validator("title", "change_note", "tags")
    @classmethod
    def steam_text(cls, value):
        values = value if isinstance(value, list) else [value]
        if any("\x00" in item for item in values):
            raise ValueError("Steam text cannot contain NUL")
        return value


class PublicationApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: StrictBool = False
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class PublicationError(ValueError):
    def __init__(self, code, message, status_code=409):
        super().__init__(message)
        self.code, self.status_code = code, status_code

    def detail(self):
        return {"code": self.code, "message": str(self)}


class PublicationVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: StrictBool = False
    resolution: Literal["item_present", "item_absent"]
    published_file_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]{0,19}$")
