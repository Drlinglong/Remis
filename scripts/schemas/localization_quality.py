"""Advanced Agent workflows separate suggestions from translation writes."""
from pydantic import Field
from typing import Literal

from .agent_batch import StrictInput


class CoverageScanRequest(StrictInput):
    project_id: str
    file_ids: list[str] = Field(min_length=1, max_length=2000)
    glossary_id: int = Field(gt=0)
    locale: str = "zh-TW"
    source_column: Literal["Text"] = "Text"
    minimum_occurrences: int = Field(default=3, ge=1, le=1000)
    example_limit: int = Field(default=3, ge=1, le=10)


class LocalizationReviewPlanRequest(StrictInput):
    translation_job_id: str
    entry_ids: list[str] | None = Field(default=None, min_length=1, max_length=500000)
    reference_project_id: str | None = None
    reference_file_ids: list[str] | None = Field(default=None, min_length=1, max_length=2000)
    reference_locale: str = "zh-CN"
    model: str = "gpt-6-luna"
    execution_mode: Literal["immediate", "background", "batch"] = "immediate"
    reasoning: dict[str, str] = Field(default_factory=lambda: {"mode": "pro", "effort": "max"})
    term_release_id: str | None = None
    allow_provisional_terms: bool = False
    group_size: int = Field(default=20, ge=1, le=100)
    max_group_chars: int = Field(default=40000, ge=1000, le=100000)
    style_guide: str = Field(default="", max_length=20000)


class ReviewStartRequest(StrictInput):
    plan_id: str
    idempotency_key: str = Field(min_length=1, max_length=200)
    approved: bool = False


class ReviewResponseReconcileRequest(StrictInput):
    custom_id: str = Field(min_length=1, max_length=200)
    response_id: str = Field(min_length=1, max_length=200)
    approved: bool = False


class ReviewEdit(StrictInput):
    find: str = Field(min_length=1)
    replace: str


class ReviewFinding(StrictInput):
    entry_label: str
    category: Literal["meaning", "referent", "mechanics", "terminology", "omission", "addition", "format", "naturalness", "reference_error"]
    severity: Literal["minor", "major", "critical"]
    confidence: Literal["high", "medium", "low"]
    explanation: str = Field(min_length=1)
    edits: list[ReviewEdit]


class ReviewGroupResult(StrictInput):
    findings: list[ReviewFinding]


class CoverageCandidateImportRequest(StrictInput):
    candidate_ids: list[str] = Field(min_length=1, max_length=500)
    approved: bool = False
