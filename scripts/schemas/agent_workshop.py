"""API schemas for deterministic validation and Agent Workshop issues."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    issue_id: Optional[str] = None
    observation_fingerprint: Optional[str] = None
    source_hash: Optional[str] = None
    target_hash: Optional[str] = None
    file_name: str
    file_id: Optional[str] = None
    file_path: Optional[str] = None
    source_file: Optional[str] = None
    key: str
    line_number: Optional[int] = None
    source_str: str
    source_context_status: Optional[str] = "found"
    source_context_origin: Optional[str] = "source_file"
    source_context_warning: Optional[str] = None
    target_str: str
    error_type: str
    error_code: Optional[str] = None
    details: str
    details_code: Optional[str] = None
    details_params: Optional[Dict[str, Any]] = None
    severity: Optional[str] = None
    requires_human_review: bool = False
    text_sample: Optional[str] = None
    workflow: Optional[str] = None
    game_id: Optional[str] = None
    project_name: Optional[str] = None
    target_lang: Optional[str] = None
    generated_at: Optional[str] = None
    status: Optional[str] = "detected"
    failure_reason: Optional[str] = None
    failure_details: Optional[str] = None
    last_suggested_fix: Optional[str] = None
    last_attempt_at: Optional[str] = None
    classification: Optional[str] = None
    repairable: bool = True
    repair_queue: bool = True
    review_queue: bool = False
    disposition: Optional[str] = "detected"
    assessment: Optional[Dict[str, Any]] = None
    attempts: int = 0


__all__ = ["ValidationIssue"]
