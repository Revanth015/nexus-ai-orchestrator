from __future__ import annotations

from pydantic import BaseModel, Field
from .manager_decision import decide as manager_decide
from .worker_learning import task_performance
from .worker_router import route_task


class ManagerExecutionDecision(BaseModel):
    action: str
    rationale: str
    confidence: float
    estimated_value: float
    resource_cost: float
    verification_required: bool
    collaboration_required: bool
    selected_worker_id: str | None = None


def decide_worker_for_task(task_type: str, *, free_only: bool = True, budget_remaining: int = 10) -> ManagerExecutionDecision:
    """Manager-first allocation: evaluate all execution-ready candidates before choosing one."""
    route = route_task(task_type, free_only=free_only)
    candidates = [c for c in route.candidates if c.execution_ready and c.eligible_for_task]
    if not candidates:
        return ManagerExecutionDecision(action="STOP", rationale=f"No execution-ready worker is available for {task_type}.", confidence=0, estimated_value=0, resource_cost=0, verification_required=False, collaboration_required=False)

    evidence = []
    for candidate in candidates:
        performance = task_performance(candidate.worker_id, task_type)
        evidence.append((candidate, performance))

    ranked = sorted(evidence, key=lambda item: (item[1].get("score", 0), item[1].get("confidence", 0), item[0].score), reverse=True)
    best, performance = ranked[0]
    decision = manager_decide(
        task_type=task_type,
        complexity=25,
        confidence=performance.get("confidence", 0),
        quality_risk=35,
        worker_score=performance.get("score", 0),
        collaboration_score=0,
        latency_ms=performance.get("avg_latency_ms", 0),
        budget_remaining=budget_remaining,
        evidence_gap=100 - performance.get("confidence", 0),
    )
    if decision.action == "STOP":
        selected = None
    else:
        selected = best.worker_id
    return ManagerExecutionDecision(**decision.__dict__, selected_worker_id=selected)
