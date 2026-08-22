from __future__ import annotations

from pydantic import BaseModel, Field
from .models import CorporateRole, WorkerProfile
from .worker_learning import learned_adjustments
from .worker_registry import list_workers

_CAPABILITY_FOR_TASK = {
    "research": "research", "file_analysis": "documents", "data_analysis": "data_analysis",
    "writing": "documents", "presentation": "presentation", "image_generation": "vision",
    "coding": "coding", "quality_review": "reasoning", "general_reasoning": "reasoning",
}

_SPECIALIZED_EXECUTORS = {
    "research": "perplexity",
    "file_analysis": "local-tools",
    "data_analysis": "local-tools",
    "quality_review": "local-validator",
}

class WorkerCandidate(BaseModel):
    worker_id: str
    name: str
    corporate_role: str
    eligible_for_task: bool
    score: float
    capability_score: float
    execution_ready: bool
    resource_status: str
    reason: str

class WorkerRouteResponse(BaseModel):
    task_type: str
    capability: str
    required_role: str
    best_profile_worker_id: str | None = None
    recommended_worker_id: str | None = None
    execution_ready: bool = False
    candidates: list[WorkerCandidate] = Field(default_factory=list)
    fallback_worker_id: str | None = None
    routing_policy: str = "free_first_role_aware_dynamic_v5"


def _capability_score(worker: WorkerProfile, capability: str) -> float:
    return float(getattr(worker.capabilities, capability, None) or 0)


def _score(worker: WorkerProfile, capability: str, task_type: str) -> float:
    capability_score = _capability_score(worker, capability)
    learned = learned_adjustments(worker.worker_id, task_type)
    reliability = max(0.0, min(100.0, float(worker.capabilities.reliability or 0) + learned["reliability"]))
    efficiency = max(0.0, min(100.0, float(worker.capabilities.efficiency or 0) + learned["efficiency"]))
    readiness_bonus = 15 if worker.metadata.get("connected", False) else 0
    return round(min(100.0, capability_score * .65 + reliability * .20 + efficiency * .10 + readiness_bonus), 2)


def route_task(task_type: str, *, free_only: bool = True) -> WorkerRouteResponse:
    capability = _CAPABILITY_FOR_TASK.get(task_type, "reasoning")
    required_role = CorporateRole.QA_EMPLOYEE.value if task_type == "quality_review" else CorporateRole.EMPLOYEE.value
    workers = [worker for worker in list_workers() if worker.enabled]
    if free_only:
        workers = [worker for worker in workers if worker.resource.free_status.value not in {"paid", "exhausted"}]

    candidates: list[WorkerCandidate] = []
    for worker in workers:
        eligible = worker.corporate_role.value == required_role
        candidates.append(WorkerCandidate(
            worker_id=worker.worker_id,
            name=worker.name,
            corporate_role=worker.corporate_role.value,
            eligible_for_task=eligible,
            score=_score(worker, capability, task_type) if eligible else 0.0,
            capability_score=_capability_score(worker, capability),
            execution_ready=bool(worker.metadata.get("execution_ready", False)),
            resource_status=worker.resource.free_status.value,
            reason=(
                "Dedicated QA employee" if task_type == "quality_review" and eligible else
                "Specialized employee executor" if _SPECIALIZED_EXECUTORS.get(task_type) == worker.worker_id and eligible else
                f"Strong {capability} fit" if eligible and _capability_score(worker, capability) >= 90 else
                f"Useful {capability} capability" if eligible else
                f"Role excluded: {worker.corporate_role.value} cannot perform {required_role} task"
            ),
        ))

    eligible_candidates = sorted([c for c in candidates if c.eligible_for_task], key=lambda item: item.score, reverse=True)
    executable = [candidate for candidate in eligible_candidates if candidate.execution_ready]
    best_profile = eligible_candidates[0] if eligible_candidates else None
    specialized_id = _SPECIALIZED_EXECUTORS.get(task_type)
    specialized = next((candidate for candidate in executable if candidate.worker_id == specialized_id), None)
    recommended = specialized or (executable[0] if executable else None)
    fallback = next((candidate.worker_id for candidate in executable if not recommended or candidate.worker_id != recommended.worker_id), None) if recommended else None

    return WorkerRouteResponse(
        task_type=task_type,
        capability=capability,
        required_role=required_role,
        best_profile_worker_id=best_profile.worker_id if best_profile else None,
        recommended_worker_id=recommended.worker_id if recommended else None,
        execution_ready=bool(recommended),
        candidates=candidates,
        fallback_worker_id=fallback,
    )
