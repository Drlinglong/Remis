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


class TaskSummary(BaseModel):
    task_id: str
    kind: str = "task"
    project_id: Optional[str] = None
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
    progress: int = Field(default=0, ge=0, le=100)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message: Optional[str] = None
    attention_reason: Optional[str] = None
    checkpoint: TaskCheckpoint = Field(default_factory=TaskCheckpoint)
    result: TaskResult = Field(default_factory=TaskResult)
    blocking: bool = False
    dedupe_key: Optional[str] = None
    idempotency_key: Optional[str] = None
    source_route: str = "/"
    allowed_actions: List[str] = Field(default_factory=list)


class TaskSummaryList(BaseModel):
    tasks: List[TaskSummary] = Field(default_factory=list)
    active_count: int = 0
    attention_count: int = 0
