from __future__ import annotations

from pydantic import BaseModel, Field
from .models import WorkerProfile
from .worker_learning import learned_adjustments, task_performance
from .worker_registry import list_workers

_CAPABILITY_FOR_TASK = {
    "research": "research", "file_analysis": "documents", "data_analysis": "data_analysis",
    "writing": "documents", "presentation": "presentation", "image_generation": "vision",
    "coding": "coding", "quality_review": "reasoning", "general_reasoning": "reasoning",
}

class WorkerCandidate(BaseModel):
    worker_id: str
    name: str
    score: float
    capability_score: float
    task_performance_score: float
    confidence: float
    execution_ready: bool
    resource_status: str
    eligible: bool
    reason: str

class WorkerRouteResponse(BaseModel):
    task_type: str
    capability: str
    best_profile_worker_id: str | None = None
    recommended_worker_id: str | None = None
    execution_ready: bool = False
    candidates: list[WorkerCandidate] = Field(default_factory=list)
    fallback_worker_id: str | None = None
    routing_policy: str = "dynamic_task_specific_performance_v6"


def _capability_score(worker: WorkerProfile, capability: str) -> float:
    return float(getattr(worker.capabilities, capability, None) or 0)


def _score(worker: WorkerProfile, capability: str, task_type: str) -> tuple[float, dict[str, float]]:
    prior = _capability_score(worker, capability)
    performance = task_performance(worker.worker_id, task_type)
    learned = learned_adjustments(worker.worker_id, task_type)
    reliability = max(0.0, min(100.0, float(worker.capabilities.reliability or 0) + learned["reliability"]))
    efficiency = max(0.0, min(100.0, float(worker.capabilities.efficiency or 0) + learned["efficiency"]))
    evidence = performance["score"] if performance["observations"] else prior
    # As evidence accumulates, observed task performance progressively outweighs the onboarding prior.
    evidence_weight = min(0.85, performance["observations"] / 20.0 * 0.85)
    blended = prior * (1.0 - evidence_weight) + evidence * evidence_weight
    score = blended * 0.65 + reliability * 0.20 + efficiency * 0.10 + (15 if worker.metadata.get("execution_ready", False) else 0)
    return round(min(100.0, score), 2), performance


def route_task(task_type: str, *, free_only: bool = True) -> WorkerRouteResponse:
    capability = _CAPABILITY_FOR_TASK.get(task_type, "reasoning")
    workers = [worker for worker in list_workers() if worker.enabled]
    if free_only:
        workers = [worker for worker in workers if worker.resource.free_status.value not in {"paid", "exhausted"}]

    candidates: list[WorkerCandidate] = []
    for worker in workers:
        score, performance = _score(worker, capability, task_type)
        candidates.append(WorkerCandidate(
            worker_id=worker.worker_id,
            name=worker.name,
            score=score,
            capability_score=_capability_score(worker, capability),
            task_performance_score=performance["score"],
            confidence=performance["confidence"],
            execution_ready=bool(worker.metadata.get("execution_ready", False)),
            resource_status=worker.resource.free_status.value,
            eligible=True,
            reason=(
                f"Best observed fit: {performance['score']:.1f} with {int(performance['observations'])} task observations" if performance["observations"] else
                f"Onboarding capability prior: {_capability_score(worker, capability):.1f}; insufficient task evidence"
            ),
        ))

    ranked = sorted(candidates, key=lambda c: (c.execution_ready, c.score, c.confidence), reverse=True)
    executable = [c for c in ranked if c.execution_ready]
    best_profile = ranked[0] if ranked else None
    recommended = executable[0] if executable else None
    fallback = executable[1].worker_id if len(executable) > 1 else None

    return WorkerRouteResponse(
        task_type=task_type,
        capability=capability,
        best_profile_worker_id=best_profile.worker_id if best_profile else None,
        recommended_worker_id=recommended.worker_id if recommended else None,
        execution_ready=bool(recommended),
        candidates=ranked,
        fallback_worker_id=fallback,
    )
