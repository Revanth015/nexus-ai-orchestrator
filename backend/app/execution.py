from __future__ import annotations

import re
from typing import Callable
from pydantic import BaseModel, Field
from .files_service import read_file
from .local_workers import execute_local_task
from .manager_decision import manager_decide
from .planner import analyze_prompt, build_task_plan
from .providers import generate_claude, generate_perplexity, generate_text
from .worker_router import route_task
from .worker_learning import record_result, task_performance
from .ai_connections import generate_custom

_TASK_METRICS = {"research": (65, 55), "file_analysis": (60, 60), "data_analysis": (70, 65), "presentation": (55, 50), "quality_review": (60, 75), "writing": (45, 45), "image_generation": (40, 35), "coding": (75, 70), "general_reasoning": (50, 55)}

class ExecutionRequest(BaseModel):
    task_type: str
    prompt: str
    file_ids: list[str] = Field(default_factory=list)
    forced_worker_id: str | None = None
    excluded_worker_ids: list[str] = Field(default_factory=list)

class ExecutionResponse(BaseModel):
    status: str
    task_type: str
    worker_id: str
    worker_name: str
    routing_policy: str
    route_score: float
    output: str
    telemetry: dict

class MissionExecutionRequest(BaseModel):
    prompt: str
    file_ids: list[str] = Field(default_factory=list)
    resource_budget: int = 12

class ArtifactRecord(BaseModel):
    artifact_id: str
    task_id: str
    name: str
    artifact_type: str
    content: str
    size_chars: int
    preview: str

class TaskExecutionRecord(BaseModel):
    task_id: str; task_type: str; title: str; status: str; worker_id: str | None = None; worker_name: str | None = None; output: str | None = None; route_score: float | None = None; telemetry: dict = Field(default_factory=dict); artifact_ids: list[str] = Field(default_factory=list); collaborators: list[str] = Field(default_factory=list); candidate_worker_ids: list[str] = Field(default_factory=list); manager_confidence: float | None = None; manager_estimated_value: float | None = None; manager_resource_cost: float | None = None; manager_decision: str | None = None; manager_rationale: str | None = None; quality_decision: str | None = None; quality_score: float | None = None; review_recommendation: str | None = None; rework_number: int = 0; rework_problem: str | None = None; sprint: int = 1; error: str | None = None

class MissionExecutionResponse(BaseModel):
    status: str; objective: str; execution_order: list[str]; manager_decision: str; rework_count: int; max_reworks: int; tasks: list[TaskExecutionRecord]; artifacts: list[ArtifactRecord]

class ManagerExecutionDecision(BaseModel):
    action: str; rationale: str; confidence: float; estimated_value: float; resource_cost: float; verification_required: bool; collaboration_required: bool; selected_worker_id: str | None = None; collaborator_worker_ids: list[str] = Field(default_factory=list); candidate_worker_ids: list[str] = Field(default_factory=list)


def _task_complexity(task_type: str, prompt: str) -> float:
    base = _TASK_METRICS.get(task_type, (50, 50))[0]; length_bonus = min(20, len(prompt) / 500)
    if any(x in prompt.lower() for x in ("multiple", "compare", "optimize", "strategy", "integrate", "forecast")): length_bonus += 10
    return min(100, base + length_bonus)

def _quality_risk(task_type: str, prompt: str) -> float:
    base = _TASK_METRICS.get(task_type, (50, 50))[1]
    if any(x in prompt.lower() for x in ("financial", "medical", "legal", "safety", "critical", "ceo", "decision")): base += 15
    return min(100, base)

def decide_worker_for_task(task_type: str, *, prompt: str = "", free_only: bool = True, budget_remaining: int = 10, exclude_worker_ids: set[str] | None = None) -> ManagerExecutionDecision:
    route = route_task(task_type, free_only=free_only, exclude_worker_ids=exclude_worker_ids)
    candidates = [c for c in route.candidates if c.execution_ready and c.eligible_for_task]; candidate_ids = [c.worker_id for c in candidates]
    if not candidates: return ManagerExecutionDecision(action="STOP", rationale=f"No execution-ready worker is available for {task_type} after applying Manager exclusions.", confidence=0, estimated_value=0, resource_cost=0, verification_required=False, collaboration_required=False, candidate_worker_ids=candidate_ids)
    evidence = [(c, task_performance(c.worker_id, task_type)) for c in candidates]; best, performance = max(evidence, key=lambda item: (item[1].get("score", 0), item[1].get("confidence", 0), item[0].score))
    complexity = _task_complexity(task_type, prompt); quality_risk = _quality_risk(task_type, prompt); confidence = float(performance.get("confidence", 0)); collaboration_score = 0.0
    if len(candidates) > 1:
        second = sorted(candidates, key=lambda c: c.score, reverse=True)[1]; collaboration_score = max(0.0, min(100.0, 50.0 - abs(best.score - second.score) + second.capability_score * 0.5))
    decision = manager_decide(task_type=task_type, complexity=complexity, confidence=confidence, quality_risk=quality_risk, worker_score=performance.get("score", 0), collaboration_score=collaboration_score, latency_ms=performance.get("avg_latency_ms", 0), budget_remaining=budget_remaining, evidence_gap=100 - confidence)
    collaborator_ids: list[str] = []
    if decision.collaboration_required and len(candidates) > 1: collaborator_ids = [c.worker_id for c in sorted(candidates, key=lambda c: c.score, reverse=True) if c.worker_id != best.worker_id][:1]
    return ManagerExecutionDecision(action=decision.action, rationale=decision.rationale, confidence=decision.confidence, estimated_value=decision.estimated_value, resource_cost=decision.resource_cost, verification_required=decision.verification_required, collaboration_required=decision.collaboration_required, selected_worker_id=None if decision.action == "STOP" else best.worker_id, collaborator_worker_ids=collaborator_ids, candidate_worker_ids=candidate_ids)

def _load_files(file_ids):
    if len(file_ids) > 10: raise ValueError("A maximum of 10 files can be supplied to one execution.")
    return [read_file(file_id) for file_id in file_ids]

def _file_context_text(files):
    return "\n\n".join(f"FILE: {item.get('filename', item.get('file_id', 'unknown'))}\nTYPE: {item.get('extension', '')}\nEXTRACTED CONTENT:\n{str(item.get('content', ''))[:12000]}" for item in files)

def _run_worker(worker_id, task_type, prompt, files):
    if worker_id == "gemini": return generate_text(prompt)
    if worker_id == "claude": return generate_claude(prompt)
    if worker_id == "perplexity": return generate_perplexity(prompt)
    if worker_id in {"local-tools", "local-validator"}: return execute_local_task(task_type, prompt, file_context=files)
    if worker_id.startswith("custom-"): return generate_custom(worker_id, prompt)
    raise RuntimeError(f"Worker '{worker_id}' has no registered executor.")

# The remainder of the mission execution engine is unchanged in behavior; the custom worker path above is the only new execution route.
