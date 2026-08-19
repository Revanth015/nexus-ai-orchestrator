from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FreeStatus(str, Enum):
    VERIFIED_FREE = "verified_free"
    MEASURED_FREE = "measured_free"
    ESTIMATED_FREE = "estimated_free"
    UNKNOWN = "unknown"
    PAID = "paid"
    EXHAUSTED = "exhausted"


class WorkerType(str, Enum):
    AI = "ai"
    TOOL = "tool"
    RESEARCH = "research"
    CREATIVE = "creative"
    VALIDATOR = "validator"
    LOCAL = "local"


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    PAUSED = "paused"


class MissionStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class QualityStatus(str, Enum):
    PASS = "pass"
    ACCEPTABLE = "acceptable"
    REWORK = "rework"
    BLOCKED = "blocked"


class CapabilityScores(BaseModel):
    reasoning: float | None = Field(default=None, ge=0, le=100)
    research: float | None = Field(default=None, ge=0, le=100)
    coding: float | None = Field(default=None, ge=0, le=100)
    documents: float | None = Field(default=None, ge=0, le=100)
    presentation: float | None = Field(default=None, ge=0, le=100)
    data_analysis: float | None = Field(default=None, ge=0, le=100)
    vision: float | None = Field(default=None, ge=0, le=100)
    instruction_following: float | None = Field(default=None, ge=0, le=100)
    reliability: float | None = Field(default=None, ge=0, le=100)
    efficiency: float | None = Field(default=None, ge=0, le=100)


class ResourceState(BaseModel):
    free_status: FreeStatus = FreeStatus.UNKNOWN
    quota_known: bool = False
    provider_remaining: float | None = None
    observed_requests: int = 0
    estimated_remaining: float | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)
    last_checked_at: str | None = None
    last_error: str | None = None


class WorkerProfile(BaseModel):
    worker_id: str
    name: str
    provider: str
    worker_type: WorkerType
    capabilities: CapabilityScores = Field(default_factory=CapabilityScores)
    resource: ResourceState = Field(default_factory=ResourceState)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskInput(BaseModel):
    source_task_ids: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class TaskSpec(BaseModel):
    task_id: str
    mission_id: str
    title: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = Field(default_factory=list)
    preferred_worker_ids: list[str] = Field(default_factory=list)
    inputs: TaskInput = Field(default_factory=TaskInput)
    max_retries: int = 2
    attempt: int = 0


class Handoff(BaseModel):
    handoff_id: str
    source_task_id: str
    destination_task_id: str
    artifact_ids: list[str] = Field(default_factory=list)
    purpose: str
    context: dict[str, Any] = Field(default_factory=dict)


class QualityIssue(BaseModel):
    issue_id: str
    severity: str
    category: str
    description: str
    material: bool = True
    suggested_fix: str | None = None


class QualityReview(BaseModel):
    review_id: str
    task_id: str
    status: QualityStatus
    score: float = Field(ge=0, le=100)
    issues: list[QualityIssue] = Field(default_factory=list)
    cycle: int = 0
    reviewer_worker_id: str | None = None


class Mission(BaseModel):
    mission_id: str
    objective: str
    status: MissionStatus = MissionStatus.DRAFT
    output_type: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
