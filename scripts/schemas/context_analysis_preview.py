"""Read-only contracts for inspecting an unpublished context analysis run."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContextAnalysisPreviewRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    project_id: str
    task_id: str | None = None
    status: str
    phase: str
    publication_status: str
    source_snapshot_hash: str
    analysis_scope: dict[str, Any] = Field(default_factory=dict)
    provider_id: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    created_at: str
    updated_at: str


class ContextAnalysisPreviewEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    aggregate_id: str
    aggregate_key: str
    aggregate_type: Literal["entity", "event"]
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    summary_evidence_source_item_ids: list[str] = Field(default_factory=list)


class ContextAnalysisPreview(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    run: ContextAnalysisPreviewRun
    published: Literal[False] = False
    warning_code: Literal["unpublished_analysis_preview"] = "unpublished_analysis_preview"
    counts: dict[str, int] = Field(default_factory=dict)
    entries: list[ContextAnalysisPreviewEntry] = Field(default_factory=list)
