from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


ModelArenaRunStatus = Literal[
    "draft",
    "queued",
    "running",
    "voting",
    "completed",
    "partial_failed",
    "failed",
    "abandoned",
]
ModelArenaVerdict = Literal["winner", "tie", "reject_all", "unjudgeable"]


class ModelArenaContestantSelection(BaseModel):
    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)


class CreateModelArenaRunRequest(BaseModel):
    project_id: str = Field(min_length=1)
    target_lang_code: str = Field(min_length=1)
    contestants: List[ModelArenaContestantSelection] = Field(min_length=2, max_length=3)
    sample_size: int = Field(default=6, ge=3, le=12)
    use_project_glossaries: bool = True
    use_mod_context: bool = True
    sample_seed: Optional[str] = None

    @model_validator(mode="after")
    def contestants_must_be_distinct(self):
        identities = {
            (contestant.provider_id, contestant.model_id)
            for contestant in self.contestants
        }
        if len(identities) != len(self.contestants):
            raise ValueError("Contestants must use distinct provider and model combinations")
        return self


class StartModelArenaRunRequest(BaseModel):
    confirmed_model_calls: bool
    idempotency_key: str = Field(min_length=1)


class RetryModelArenaFailuresRequest(StartModelArenaRunRequest):
    pass


class ModelArenaVoteRequest(BaseModel):
    verdict: ModelArenaVerdict
    winner_output_id: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    note: Optional[str] = None

    @model_validator(mode="after")
    def winner_matches_verdict(self):
        if self.verdict == "winner" and not self.winner_output_id:
            raise ValueError("winner_output_id is required for a winner verdict")
        if self.verdict != "winner" and self.winner_output_id is not None:
            raise ValueError("winner_output_id is only valid for a winner verdict")
        return self


class ModelArenaCandidate(BaseModel):
    candidate_id: str
    entry_key: str
    relative_file_path: str
    line_number: Optional[int] = None
    source_text: str
    source_sha256: str
    feature_tags: List[str] = Field(default_factory=list)


class ModelArenaSample(BaseModel):
    sample_id: str
    ordinal: int
    entry_key: str
    relative_file_path: str
    line_number: Optional[int] = None
    source_text: str
    source_sha256: str
    feature_tags: List[str] = Field(default_factory=list)
    display_permutation: List[str] = Field(default_factory=list)


class ModelArenaContestant(BaseModel):
    contestant_id: str
    provider_id: str
    model_id: str
    execution_order: int
    config_snapshot: Dict[str, Any] = Field(default_factory=dict)
    config_fingerprint: str
    prompt_fingerprint: str
    status: str = "draft"
    request_count: int = 0
    elapsed_ms: Optional[int] = None
    failure_code: Optional[str] = None


class ModelArenaRequestEvidence(BaseModel):
    request_id: str
    contestant_id: str
    batch_ordinal: int
    system_instruction: Optional[str] = None
    prompt_text: str
    effective_parameters: Dict[str, Any] = Field(default_factory=dict)
    prompt_sha256: str
    completion_text_before_parse: Optional[str] = None
    completion_source: str
    completion_sha256: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    parse_status: str
    failure_code: Optional[str] = None
    elapsed_ms: Optional[int] = None
    created_at: str


class ModelArenaOutput(BaseModel):
    output_id: str
    sample_id: str
    contestant_id: str
    translated_text: Optional[str] = None
    response_sha256: Optional[str] = None
    parse_status: str
    hard_error_count: int = 0
    validation: List[Dict[str, Any]] = Field(default_factory=list)


class ModelArenaVote(BaseModel):
    vote_id: str
    sample_id: str
    verdict: ModelArenaVerdict
    winner_output_id: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    note: Optional[str] = None
    created_at: str
    updated_at: str


class ModelArenaEvent(BaseModel):
    event_id: Optional[int] = None
    run_id: str
    sequence: Optional[int] = None
    timestamp: str
    level: str = "info"
    event_type: str
    failure_code: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class ModelArenaRun(BaseModel):
    run_id: str
    project_id: Optional[str] = None
    project_name_snapshot: str
    game_id: str
    source_lang_code: str
    target_lang_code: str
    sample_seed: str
    sampler_version: str
    sample_size: int
    eligible_count: int
    status: ModelArenaRunStatus
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    contestants: List[ModelArenaContestant] = Field(default_factory=list)
    samples: List[ModelArenaSample] = Field(default_factory=list)
    requests: List[ModelArenaRequestEvidence] = Field(default_factory=list)
    outputs: List[ModelArenaOutput] = Field(default_factory=list)
    votes: List[ModelArenaVote] = Field(default_factory=list)
    events: List[ModelArenaEvent] = Field(default_factory=list)


class ModelArenaContestantResponse(BaseModel):
    candidate_id: Optional[str] = None
    contestant_id: Optional[str] = None
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    execution_order: Optional[int] = None
    config_snapshot: Dict[str, Any] = Field(default_factory=dict)
    config_fingerprint: Optional[str] = None
    prompt_fingerprint: Optional[str] = None
    status: str = "draft"
    request_count: int = 0
    elapsed_ms: Optional[int] = None
    failure_code: Optional[str] = None


class ModelArenaSampleResponse(BaseModel):
    sample_id: str
    ordinal: int
    entry_key: Optional[str] = None
    relative_file_path: Optional[str] = None
    line_number: Optional[int] = None
    source_text: str
    source_sha256: str
    feature_tags: List[str] = Field(default_factory=list)
    display_permutation: List[str] = Field(default_factory=list)


class ModelArenaOutputResponse(BaseModel):
    output_id: str
    sample_id: str
    contestant_id: Optional[str] = None
    candidate_id: Optional[str] = None
    translated_text: Optional[str] = None
    response_sha256: Optional[str] = None
    parse_status: str
    hard_error_count: int = 0
    validation: List[Dict[str, Any]] = Field(default_factory=list)


class ModelArenaEventResponse(BaseModel):
    event_id: Optional[int] = None
    run_id: Optional[str] = None
    sequence: Optional[int] = None
    timestamp: str
    level: str = "info"
    event_type: str
    failure_code: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class ModelArenaRunResponse(BaseModel):
    run_id: str
    project_id: Optional[str] = None
    project_name_snapshot: str
    game_id: str
    source_lang_code: str
    target_lang_code: str
    sample_seed: str
    sampler_version: str
    sample_size: int
    eligible_count: int
    status: ModelArenaRunStatus
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    contestants: List[ModelArenaContestantResponse] = Field(default_factory=list)
    samples: List[ModelArenaSampleResponse] = Field(default_factory=list)
    requests: List[ModelArenaRequestEvidence] = Field(default_factory=list)
    outputs: List[ModelArenaOutputResponse] = Field(default_factory=list)
    votes: List[ModelArenaVote] = Field(default_factory=list)
    events: List[ModelArenaEventResponse] = Field(default_factory=list)
    results: Optional[Dict[str, Any]] = None
    request_batch_count: int = 0
    estimated_request_count: int = 0


class ModelArenaRunList(BaseModel):
    runs: List[ModelArenaRun] = Field(default_factory=list)
    total_count: int = 0


class ModelArenaRunListResponse(BaseModel):
    runs: List[ModelArenaRunResponse] = Field(default_factory=list)
    total_count: int = 0


class ModelArenaTaskPreparationResponse(BaseModel):
    run_id: str
    task_id: Optional[str] = None
    status: str
    idempotent_replay: bool = False


class ModelArenaRedaction(BaseModel):
    type: str
    count: int


class ModelArenaExportPreview(BaseModel):
    schema_version: str
    exported_at: str
    export_mode: Literal["evidence", "summary-only"]
    remis_version: str
    redactions: List[ModelArenaRedaction] = Field(default_factory=list)
    arena_run: Dict[str, Any]
