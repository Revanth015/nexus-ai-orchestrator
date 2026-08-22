from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ManagerDecision:
    action: str
    rationale: str
    confidence: float
    estimated_value: float
    resource_cost: float
    verification_required: bool
    collaboration_required: bool


def decide(*, task_type: str, complexity: float, confidence: float, quality_risk: float, worker_score: float, collaboration_score: float = 0.0, latency_ms: float = 0.0, budget_remaining: int = 10, evidence_gap: float = 0.0) -> ManagerDecision:
    """Choose the smallest workforce likely to achieve the task while accounting for task-specific risk and evidence."""
    complexity = max(0.0, min(100.0, complexity))
    confidence = max(0.0, min(100.0, confidence))
    quality_risk = max(0.0, min(100.0, quality_risk))
    worker_score = max(0.0, min(100.0, worker_score))
    collaboration_score = max(0.0, min(100.0, collaboration_score))
    evidence_gap = max(0.0, min(100.0, evidence_gap))

    if budget_remaining <= 0:
        return ManagerDecision("STOP", "Mission resource budget is exhausted.", confidence, 0, 0, False, False)

    verification = quality_risk >= 70 or complexity >= 80 or confidence < 45
    collaboration = (complexity >= 65 and collaboration_score >= 55) or evidence_gap >= 55

    if worker_score < 60:
        action = "EXPLORE"
        rationale = "No established worker has sufficient task-specific evidence; allocate controlled exploratory work."
    elif verification:
        action = "ASSIGN_AND_VERIFY"
        rationale = "Task-specific complexity, quality risk, or low confidence justifies independent verification."
    elif collaboration:
        action = "COLLABORATE"
        rationale = "Task-specific complexity or evidence gap makes a second employee likely to add measurable value."
    else:
        action = "ASSIGN"
        rationale = "A proven worker can complete this task without unnecessary additional AI calls."

    estimated_value = max(0.0, min(100.0, worker_score * 0.55 + confidence * 0.25 + complexity * 0.10 + collaboration_score * 0.10))
    resource_cost = 1.0 + (1.0 if collaboration else 0.0) + (1.0 if verification else 0.0)
    if latency_ms > 8000:
        rationale += " Worker latency is high, so additional calls should be justified by expected quality gain."

    return ManagerDecision(action, rationale, round(confidence, 2), round(estimated_value, 2), resource_cost, verification, collaboration)


def decision_payload(decision: ManagerDecision) -> dict[str, Any]:
    return {
        "action": decision.action,
        "rationale": decision.rationale,
        "confidence": decision.confidence,
        "estimated_value": decision.estimated_value,
        "resource_cost": decision.resource_cost,
        "verification_required": decision.verification_required,
        "collaboration_required": decision.collaboration_required,
    }
