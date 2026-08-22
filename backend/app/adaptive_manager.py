from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MissionEvent:
    kind: str
    task_id: str
    detail: str
    sprint: int


@dataclass
class AdaptiveMissionState:
    objective: str
    sprint: int = 1
    events: list[MissionEvent] = field(default_factory=list)
    replans: int = 0
    rework_count: int = 0
    max_reworks: int = 3

    def record(self, kind: str, task_id: str, detail: str, sprint: int | None = None) -> None:
        self.events.append(MissionEvent(kind, task_id, detail, sprint or self.sprint))

    def observe_failure(self, task_id: str, detail: str) -> dict[str, Any]:
        self.sprint += 1
        self.replans += 1
        self.record("failure", task_id, detail)
        return self.replan_decision("execution_failure", task_id, detail)

    def observe_missing_input(self, task_id: str, detail: str) -> dict[str, Any]:
        self.sprint += 1
        self.replans += 1
        self.record("missing_input", task_id, detail)
        return self.replan_decision("missing_input", task_id, detail)

    def observe_qa(self, task_id: str, recommendation: str, problem: str | None) -> dict[str, Any]:
        if recommendation == "PASS":
            self.record("qa_pass", task_id, "Independent review passed; Manager may accept the artifact.")
            return {"action": "accept_candidate", "replan": False, "reason": "QA passed."}
        if self.rework_count >= self.max_reworks:
            self.record("rework_limit", task_id, problem or "QA requested rework.")
            return {"action": "escalate_stop", "replan": False, "reason": "Maximum of three reworks reached."}
        self.rework_count += 1
        self.sprint += 1
        self.replans += 1
        detail = problem or "QA requested rework without a specific problem."
        self.record("qa_rework", task_id, detail)
        return {"action": "create_rework_and_review", "replan": True, "rework_number": self.rework_count, "problem": detail, "sprint": self.sprint}

    def replan_decision(self, trigger: str, task_id: str, detail: str) -> dict[str, Any]:
        return {
            "action": "manager_replan",
            "replan": True,
            "trigger": trigger,
            "source_task": task_id,
            "reason": detail,
            "sprint": self.sprint,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "sprint": self.sprint,
            "replans": self.replans,
            "rework_count": self.rework_count,
            "max_reworks": self.max_reworks,
            "events": [event.__dict__ for event in self.events],
        }


def classify_replan_signal(*, status: str, missing_inputs: list[str] | None = None, qa_recommendation: str | None = None, qa_problem: str | None = None) -> dict[str, Any]:
    """Convert execution observations into a Manager-level replanning signal."""
    if qa_recommendation == "REWORK":
        return {"trigger": "qa_rework", "detail": qa_problem or "QA requested rework."}
    if missing_inputs:
        return {"trigger": "missing_input", "detail": f"Missing inputs: {', '.join(missing_inputs)}"}
    if status == "failed":
        return {"trigger": "execution_failure", "detail": "Task execution failed and requires Manager reassessment."}
    return {"trigger": None, "detail": None}
