from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


ReviewSelection = Literal["left", "right", "tie", "uncertain", "skip"]


class ArchiveABReviewRequest(BaseModel):
    manifest_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    selection: ReviewSelection
    error_tags: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    note: Optional[str] = Field(default="", max_length=4000)
