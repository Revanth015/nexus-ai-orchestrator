from __future__ import annotations

from pydantic import BaseModel, Field


class PlanTask(BaseModel):
    task_id: str
    title: str
    task_type: str
    status: str = "ready"
    dependencies: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    preferred_worker_types: list[str] = Field(default_factory=list)
    quality_gate: bool = False


class TaskPlan(BaseModel):
    objective: str
    tasks: list[PlanTask] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    planner: str = "local_graph_v1"


class PlanResponse(BaseModel):
    plan: TaskPlan
