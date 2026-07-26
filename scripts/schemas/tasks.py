from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TaskCreator(BaseModel):
    type: Literal["user", "remis_agent", "automation", "system"] = "user"
    actor_id: Optional[str] = None
    label: Optional[str] = None


class TaskCheckpoint(BaseModel):
    available: bool = False
    resume_supported: bool = False
    stage: str = ""
    cursor: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    types: List[str] = Field(default_factory=list)
    output_paths: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskProjectContext(BaseModel):
    name: str
    game_id: Optional[str] = None


class TaskChildAggregate(BaseModel):
    total: int = 0
    active: int = 0
    attention: int = 0
    completed: int = 0
    progress: int = Field(default=0, ge=0, le=100)


class TaskSummary(BaseModel):
    task_id: str
    kind: str = "task"
    project_id: Optional[str] = None
    project_context: Optional[TaskProjectContext] = None
    parent_task_id: Optional[str] = None
    created_by: TaskCreator = Field(default_factory=TaskCreator)
    title: str
    status: Literal[
        "queued",
        "running",
        "awaiting_approval",
        "completed",
        "failed",
        "cancelled",
        "interrupted",
        "unknown",
    ]
    stage: str = ""
    stage_code: str = ""
    progress: int = Field(default=0, ge=0, le=100)
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    finished_at: Optional[str] = None
    archived_at: Optional[str] = None
    message: Optional[str] = None
    attention_reason: Optional[str] = None
    attention_reason_code: Optional[str] = None
    checkpoint: TaskCheckpoint = Field(default_factory=TaskCheckpoint)
    result: TaskResult = Field(default_factory=TaskResult)
    blocking: bool = False
    blocking_reason: Optional[str] = None
    dedupe_key: Optional[str] = None
    idempotency_key: Optional[str] = None
    source_route: str = "/"
    workflow_context: Dict[str, Any] = Field(default_factory=dict)
    allowed_actions: List[str] = Field(default_factory=list)


class TaskSummaryList(BaseModel):
    tasks: List[TaskSummary] = Field(default_factory=list)
    active_count: int = 0
    attention_count: int = 0
    total_count: int = 0


class TaskEvent(BaseModel):
    event_id: str
    task_id: str
    sequence: int
    timestamp: Optional[str] = None
    level: Literal["debug", "info", "warning", "error", "success"] = "info"
    event_type: str = "log"
    audience: Literal["user", "diagnostic"] = "user"
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskDetail(TaskSummary):
    events: List[TaskEvent] = Field(default_factory=list)
    children: List[TaskSummary] = Field(default_factory=list)
    child_aggregate: TaskChildAggregate = Field(default_factory=TaskChildAggregate)
