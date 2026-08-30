"""Contracts for explicit Mod Archive removal."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RemoveContextArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(min_length=1, max_length=300)
    approved: bool


class RemoveContextArchiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    project_id: str
    project_name: str
    removed_counts: dict[str, int]
    preserved: list[str]
    allowed_actions: list[str]
