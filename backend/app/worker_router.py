from __future__ import annotations

from pydantic import BaseModel, Field
from .models import WorkerProfile
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
    score: float
    capability_score: float
    execution_ready: bool
    resource_status: str
    reason: str

class WorkerRouteResponse(BaseModel):
    task_type: str
    capability: str
    best_profile_worker_id: str | None = None
    recommended_worker_id: str | None = None
    execution_ready: bool = False
    candidates: list[WorkerCandidate] = Field(default_factory=list)
    fallback_worker_id: str | None = None
    routing_policy: str = "free_first_execution_aware_v4"


def _capability_score(worker: WorkerProfile, capability: str) -> float:
    return float(getattr(worker.capabilities, capability, None) or 0)


def _score(worker: WorkerProfile, capability: str) -> float:
    capability_score = _capability_score(worker, capability)
    reliability = float(worker.capabilities.reliability or 0)
    efficiency = float(worker.capabilities.efficiency or 0)
    readiness_bonus = 15 if worker.metadata.get("connected", False) else 0
    return round(min(100.0, capability_score * .65 + reliability * .20 + efficiency * .10 + readiness_bonus), 2)


def route_task(task_type: str, *, free_only: bool = True) -> WorkerRouteResponse:
    capability = _CAPABILITY_FOR_TASK.get(task_type, "reasoning")
    workers = [worker for worker in list_workers() if worker.enabled]
    if free_only:
        workers = [worker for worker in workers if worker.resource.free_status.value not in {"paid", "exhausted"}]

    candidates = sorted([
        WorkerCandidate(
            worker_id=worker.worker_id,
            name=worker.name,
            score=_score(worker, capability),
            capability_score=_capability_score(worker, capability),
            execution_ready=bool(worker.metadata.get("execution_ready", False)),
            resource_status=worker.resource.free_status.value,
            reason=("Specialized executor" if _SPECIALIZED_EXECUTORS.get(task_type) == worker.worker_id else f"Strong {capability} fit" if _capability_score(worker, capability) >= 90 else f"Useful {capability} capability"),
        ) for worker in workers
    ], key=lambda item: item.score, reverse=True)

    best_profile = candidates[0] if candidates else None
    executable = [candidate for candidate in candidates if candidate.execution_ready]
    specialized_id = _SPECIALIZED_EXECUTORS.get(task_type)
    specialized = next((candidate for candidate in executable if candidate.worker_id == specialized_id), None)
    recommended = specialized or (executable[0] if executable else None)
    fallback = next((candidate.worker_id for candidate in executable if not recommended or candidate.worker_id != recommended.worker_id), None) if recommended else None

    return WorkerRouteResponse(
        task_type=task_type,
        capability=capability,
        best_profile_worker_id=best_profile.worker_id if best_profile else None,
        recommended_worker_id=recommended.worker_id if recommended else None,
        execution_ready=bool(recommended),
        candidates=candidates,
        fallback_worker_id=fallback,
    )
