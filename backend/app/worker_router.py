from __future__ import annotations

from pydantic import BaseModel, Field

from .models import WorkerProfile
from .worker_registry import list_workers


_CAPABILITY_FOR_TASK = {
    "research": "research",
    "file_analysis": "documents",
    "data_analysis": "data_analysis",
    "writing": "documents",
    "presentation": "presentation",
    "image_generation": "vision",
    "coding": "coding",
    "quality_review": "reasoning",
    "general_reasoning": "reasoning",
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
    # best_profile_worker_id answers: "Who would be best if connected?"
    best_profile_worker_id: str | None = None
    # recommended_worker_id answers: "Who can NEXUS actually use right now?"
    recommended_worker_id: str | None = None
    execution_ready: bool = False
    candidates: list[WorkerCandidate] = Field(default_factory=list)
    fallback_worker_id: str | None = None
    routing_policy: str = "free_first_execution_aware_v2"


def _capability_score(worker: WorkerProfile, capability: str) -> float:
    value = getattr(worker.capabilities, capability, None)
    return float(value or 0)


def _score(worker: WorkerProfile, capability: str) -> float:
    capability_score = _capability_score(worker, capability)
    reliability = float(worker.capabilities.reliability or 0)
    efficiency = float(worker.capabilities.efficiency or 0)

    connected = bool(worker.metadata.get("connected", False))
    readiness_bonus = 15 if connected else 0
    raw_score = capability_score * 0.65 + reliability * 0.20 + efficiency * 0.10 + readiness_bonus
    return round(min(100.0, raw_score), 2)


def route_task(task_type: str, *, free_only: bool = True) -> WorkerRouteResponse:
    capability = _CAPABILITY_FOR_TASK.get(task_type, "reasoning")
    workers = [worker for worker in list_workers() if worker.enabled]

    if free_only:
        workers = [
            worker for worker in workers
            if worker.resource.free_status.value not in {"paid", "exhausted"}
        ]

    candidates = sorted(
        (
            WorkerCandidate(
                worker_id=worker.worker_id,
                name=worker.name,
                score=_score(worker, capability),
                capability_score=_capability_score(worker, capability),
                execution_ready=bool(worker.metadata.get("execution_ready", False)),
                resource_status=worker.resource.free_status.value,
                reason=(
                    f"Strong {capability} fit" if _capability_score(worker, capability) >= 90
                    else f"Useful {capability} capability"
                ),
            )
            for worker in workers
        ),
        key=lambda item: item.score,
        reverse=True,
    )

    # Keep the ideal profile separate from the executable route. This prevents
    # an unconnected high-scoring AI from being presented as immediately usable.
    best_profile = candidates[0] if candidates else None
    executable = [candidate for candidate in candidates if candidate.execution_ready]
    recommended = executable[0] if executable else None
    fallback = executable[1].worker_id if len(executable) > 1 else None

    return WorkerRouteResponse(
        task_type=task_type,
        capability=capability,
        best_profile_worker_id=best_profile.worker_id if best_profile else None,
        recommended_worker_id=recommended.worker_id if recommended else None,
        execution_ready=bool(recommended),
        candidates=candidates,
        fallback_worker_id=fallback,
    )
