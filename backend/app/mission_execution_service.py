from __future__ import annotations

from .audit_log import decision_record, record_event
from .execution import MissionExecutionRequest, MissionExecutionResponse, execute_mission as run_mission
from .mission_memory import add_artifact, add_decision, add_qa_finding, add_task, complete_mission, create_mission, record_resource_use, transition, update_mission


def execute_mission_with_memory(request: MissionExecutionRequest, *, free_only: bool = True) -> MissionExecutionResponse:
    mission = create_mission(request.prompt)
    mission_id = mission["mission_id"]
    record_event("mission_created", mission_id=mission_id, data={"objective": request.prompt, "resource_budget": mission["resource_budget"]})
    transition(mission_id, "ALLOCATING", reason="Manager created the mission plan.")
    try:
        result = run_mission(request, free_only=free_only)
        transition(mission_id, "EXECUTING", reason="Mission task execution completed; synchronizing mission state.")
        for task in result.tasks:
            task_data = task.model_dump(mode="json")
            add_task(mission_id, task_data)
            if task.worker_id:
                current = mission.get("active_workers", [])
                if task.worker_id not in current:
                    current.append(task.worker_id)
                    update_mission(mission_id, active_workers=current)
            record_event("task_execution", mission_id=mission_id, task_id=task.task_id, actor=task.worker_id or "nexus-manager", data={"status": task.status, "task_type": task.task_type, "worker_id": task.worker_id, "sprint": task.sprint, "rework_number": task.rework_number, "error": task.error})
            if task.manager_decision:
                decision = {"task_id": task.task_id, "decision": task.manager_decision, "worker_id": task.worker_id, "rationale": task.manager_rationale}
                add_decision(mission_id, decision)
                decision_record(mission_id=mission_id, task_id=task.task_id, task_type=task.task_type, selected_worker_id=task.worker_id, candidates=[], decision=task.manager_decision, rationale=task.manager_rationale or "Mission execution decision", confidence=0, expected_value=task.route_score or 0, resource_cost=1)
            if task.quality_decision:
                finding = {"task_id": task.task_id, "recommendation": task.quality_decision, "problem": task.rework_problem, "rework_number": task.rework_number}
                add_qa_finding(mission_id, finding)
                record_event("qa_rework" if task.quality_decision == "REWORK" else "qa_pass", mission_id=mission_id, task_id=task.task_id, actor=task.worker_id or "reviewer", data=finding)
            for artifact_id in task.artifact_ids:
                artifact = next((a for a in result.artifacts if a.artifact_id == artifact_id), None)
                if artifact:
                    add_artifact(mission_id, artifact.model_dump(mode="json"))
            if task.status in {"completed", "reviewed"}:
                record_resource_use(mission_id, 1)
        final_state = "COMPLETED" if result.status == "completed" else ("REWORK_LIMIT_REACHED" if result.status == "rework_limit_reached" else "FAILED")
        transition(mission_id, final_state, reason=f"Mission result: {result.status}")
        update_mission(mission_id, rework_count=result.rework_count, resource_used=min(mission["resource_budget"], len(result.tasks)))
        if result.status == "completed":
            complete_mission(mission_id, final_decision=result.manager_decision)
        else:
            record_event("mission_ended", mission_id=mission_id, data={"status": result.status, "manager_decision": result.manager_decision, "rework_count": result.rework_count})
        return result
    except Exception as exc:
        transition(mission_id, "FAILED", reason=str(exc))
        record_event("mission_failed", mission_id=mission_id, data={"error": str(exc)})
        raise
