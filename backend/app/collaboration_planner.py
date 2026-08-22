from __future__ import annotations

from pydantic import BaseModel, Field

from .worker_learning import learning_snapshot, task_performance
from .worker_registry import list_workers


class CollaborationDecision(BaseModel):
    mode: str
    reason: str
    max_workers: int = 1
    max_depth: int = 0
    independent_verification: bool = False
    collaboration_required: bool = False
    recommended_workers: list[str] = Field(default_factory=list)


def _task_complexity(task_type: str, prompt: str) -> float:
    text = prompt.lower()
    complexity = {
        "general_reasoning": 0.35,
        "research": 0.60,
        "data_analysis": 0.55,
        "file_analysis": 0.55,
        "writing": 0.35,
        "presentation": 0.65,
        "coding": 0.65,
        "quality_review": 0.70,
    }.get(task_type, 0.50)
    signals = ["compare", "multiple", "strategy", "recommend", "critical", "high stakes", "verify", "sources", "complex", "integrate"]
    complexity += min(0.25, sum(word in text for word in signals) * 0.025)
    if len(prompt) > 1200:
        complexity += 0.10
    return min(1.0, complexity)


def plan_collaboration(task_type: str, prompt: str, *, free_only: bool = True) -> CollaborationDecision:
    workers = [w for w in list_workers() if w.enabled and w.metadata.get("execution_ready", False)]
    if free_only:
        workers = [w for w in workers if w.resource.free_status.value not in {"paid", "exhausted"}]
    complexity = _task_complexity(task_type, prompt)
    if len(workers) <= 1:
        return CollaborationDecision(mode="single_worker", reason="Only one executable worker is currently available.")

    ranked = []
    for worker in workers:
        p = task_performance(worker.worker_id, task_type)
        ranked.append((worker.worker_id, p["score"], p["confidence"], p["observations"]))
    ranked.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)

    # Low evidence: one worker first; exploration is handled by the normal router.
    if complexity < 0.55:
        return CollaborationDecision(mode="single_worker", reason="Task complexity does not justify additional AI calls.", recommended_workers=[ranked[0][0]])

    # Medium/high complexity: parallel perspectives are useful when there is more than one credible worker.
    if complexity < 0.78:
        return CollaborationDecision(mode="parallel", reason="Moderate complexity benefits from independent perspectives before synthesis.", max_workers=min(2, len(ranked)), recommended_workers=[x[0] for x in ranked[:2]])

    return CollaborationDecision(mode="parallel_plus_verification", reason="High-complexity task warrants independent work followed by verification.", max_workers=min(3, len(ranked)), max_depth=2, independent_verification=True, collaboration_required=True, recommended_workers=[x[0] for x in ranked[:3]])


def collaboration_history() -> dict:
    data = learning_snapshot()
    return {"collaboration": data.get("collaboration", {}), "worker_count": len(data.get("workers", {}))}
