from __future__ import annotations

from pydantic import BaseModel, Field
from .models import WorkerProfile, FreeStatus
from .worker_learning import learned_adjustments, task_performance, collaboration_performance, get_worker_learning
from .worker_registry import list_workers

_CAPABILITY_FOR_TASK = {"research":"research","file_analysis":"documents","data_analysis":"data_analysis","writing":"documents","presentation":"presentation","image_generation":"vision","coding":"coding","quality_review":"reasoning","general_reasoning":"reasoning"}

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
    eligible_for_task: bool = True
    exploration: bool = False
    reason: str

class WorkerRouteResponse(BaseModel):
    task_type: str
    capability: str
    best_profile_worker_id: str | None = None
    recommended_worker_id: str | None = None
    execution_ready: bool = False
    candidates: list[WorkerCandidate] = Field(default_factory=list)
    fallback_worker_id: str | None = None
    routing_policy: str = "dynamic_task_specific_performance_v10"
    exploration_policy: str = "evidence_aware_exploration"


def _capability_score(worker: WorkerProfile, capability: str) -> tuple[float, str]:
    profile_score = float(getattr(worker.capabilities, capability, None) or 0)
    learning = get_worker_learning(worker.worker_id)
    onboarding = learning.get("onboarding", {})
    benchmark_scores = onboarding.get("benchmark_scores", {})
    benchmark_score = benchmark_scores.get(capability)
    if benchmark_score is not None and onboarding.get("status") in {"completed", "partial"}:
        return float(benchmark_score), "validated onboarding benchmark"
    return profile_score, "registered capability prior"


def _score(worker: WorkerProfile, capability: str, task_type: str) -> tuple[float, dict[str,float], bool, str]:
    prior, prior_source = _capability_score(worker, capability)
    performance = task_performance(worker.worker_id, task_type)
    learned = learned_adjustments(worker.worker_id, task_type)
    reliability = max(0, min(100, float(worker.capabilities.reliability or 0) + learned["reliability"]))
    efficiency = max(0, min(100, float(worker.capabilities.efficiency or 0) + learned["efficiency"]))
    evidence = performance["score"] if performance["observations"] else prior
    evidence_weight = min(.85, performance["observations"] / 20 * .85)
    blended = prior * (1 - evidence_weight) + evidence * evidence_weight
    exploration = performance["observations"] < 5
    exploration_bonus = 2.0 if exploration else 0.0
    score = blended * .65 + reliability * .20 + efficiency * .10 + (15 if worker.metadata.get("execution_ready", False) else 0) + exploration_bonus
    return round(min(100, score), 2), performance, exploration, prior_source


def route_task(task_type: str, *, free_only: bool = True, exclude_worker_ids: set[str] | None = None) -> WorkerRouteResponse:
    capability = _CAPABILITY_FOR_TASK.get(task_type, "reasoning")
    excluded = exclude_worker_ids or set()
    workers = [w for w in list_workers() if w.enabled and w.worker_id not in excluded]
    if free_only:
        # Free-only mode must not silently treat unknown/free-unverified providers as free.
        workers = [w for w in workers if w.resource.free_status in {
            FreeStatus.VERIFIED_FREE, FreeStatus.MEASURED_FREE, FreeStatus.ESTIMATED_FREE
        }]
    candidates = []
    for worker in workers:
        score, performance, exploration, prior_source = _score(worker, capability, task_type)
        if performance["observations"]:
            reason = f"Observed fit {performance['score']:.1f} from {int(performance['observations'])} observations; confidence {performance['confidence']:.1f}%"
        else:
            reason = f"{prior_source}: {score:.1f}; controlled exploration candidate"
        candidates.append(WorkerCandidate(
            worker_id=worker.worker_id,
            name=worker.name,
            score=score,
            capability_score=_capability_score(worker, capability)[0],
            task_performance_score=performance["score"],
            confidence=performance["confidence"],
            execution_ready=bool(worker.metadata.get("execution_ready", False)),
            resource_status=worker.resource.free_status.value,
            eligible=True,
            eligible_for_task=True,
            exploration=exploration,
            reason=reason,
        ))
    ranked = sorted(candidates, key=lambda c: (c.execution_ready, c.score, c.confidence), reverse=True)
    executable = [c for c in ranked if c.execution_ready]
    best = ranked[0] if ranked else None
    recommended = executable[0] if executable else None
    fallback = executable[1].worker_id if len(executable) > 1 else None
    return WorkerRouteResponse(
        task_type=task_type,
        capability=capability,
        best_profile_worker_id=best.worker_id if best else None,
        recommended_worker_id=recommended.worker_id if recommended else None,
        execution_ready=bool(recommended),
        candidates=ranked,
        fallback_worker_id=fallback,
    )
