"""Editable terminology uses the existing glossary; releases are snapshots."""
from typing import Literal

from pydantic import Field

from .agent_batch import StrictInput, TermDefinition


class HistoricalTermReference(StrictInput):
    workshop_id: str = Field(pattern=r"^[0-9]{1,20}$")
    source_kind: Literal["author_public_history", "subscribed_archive"] = "author_public_history"
    source_id: str = Field(min_length=1, max_length=300)
    english: str = Field(min_length=1, max_length=2000)
    translation: str = Field(min_length=1, max_length=2000)
    context: str = Field(default="", max_length=10000)
    file_path: str = Field(min_length=1, max_length=2000)
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    match_status: Literal["same_id_same_english", "same_id_changed_english", "matched_different_id"]


class ReviewedGlossaryTerm(TermDefinition):
    review_state: Literal["candidate", "reviewed", "pending", "approved", "rejected"] = "candidate"
    confidence: Literal["high", "medium", "low", "unrated"] = "unrated"
    source_id: str = Field(default="", max_length=300)
    reference_translations: dict[str, str] = Field(default_factory=dict)
    original_candidate: str = Field(default="", max_length=2000)
    audit_reason: str = Field(default="", max_length=10000)
    audit_suggestion: str = Field(default="", max_length=2000)
    historical_reference: HistoricalTermReference | None = None


class TerminologyGlossaryImport(StrictInput):
    game_id: str = Field(min_length=1, max_length=100)
    scope_id: str | None = Field(default=None, min_length=1, max_length=200)
    locale: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    import_key: str = Field(min_length=1, max_length=200)
    terms: list[ReviewedGlossaryTerm] = Field(min_length=1, max_length=50000)
    approved: bool = False


class GlossaryTermReleaseRequest(StrictInput):
    glossary_id: int = Field(gt=0)
    locale: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    version: str = Field(min_length=1, max_length=100)
    maturity: Literal["provisional", "approved"] = "provisional"
    expected_fingerprint: str = Field(min_length=64, max_length=64)
    approved: bool = False


class GlossaryTermAppendRequest(StrictInput):
    locale: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    expected_fingerprint: str = Field(min_length=64, max_length=64)
    terms: list[ReviewedGlossaryTerm] = Field(min_length=1, max_length=50000)
    approved: bool = False


class TermReviewChange(StrictInput):
    concept_id: str = Field(min_length=1, max_length=300)
    translation: str | None = Field(default=None, min_length=1, max_length=2000)
    sense: str | None = Field(default=None, min_length=1, max_length=10000)
    aliases: list[str] | None = Field(default=None, max_length=100)
    review_state: Literal["candidate", "reviewed", "pending", "approved", "rejected"]
    reason: str = Field(default="", max_length=10000)
    historical_reference: HistoricalTermReference | None = None
    confidence: Literal["high", "medium", "low", "unrated"] | None = None


class GlossaryTermReviewRequest(StrictInput):
    locale: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    expected_fingerprint: str = Field(min_length=64, max_length=64)
    reviewer: str = Field(default="manual review", min_length=1, max_length=300)
    review_origin: Literal["human", "model", "reference"] = "human"
    changes: list[TermReviewChange] = Field(min_length=1, max_length=50000)
    approved: bool = False
