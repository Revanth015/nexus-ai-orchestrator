from __future__ import annotations

from .audit_log import decision_record, record_event
from .execution import MissionExecutionRequest, MissionExecutionResponse, execute_mission as run_mission
from .mission_memory import add_artifact, add_decision, add_qa_finding, add_task, complete_mission, create_mission, record_resource_use, transition, update_mission, get_mission


def execute_mission_with_memory(request: MissionExecutionRequest, *, free_only: bool = True) -> MissionExecutionResponse:
    mission = create_mission(request.prompt, resource_budget=request.resource_budget)
    mission_id = mission["mission_id"]
    record_event("mission_created", mission_id=mission_id, data={"objective": request.prompt, "resource_budget": mission["resource_budget"]})
    transition(mission_id, "ALLOCATING", reason="Manager created the mission plan.")

    def sync_state(state: str, data: dict) -> None:
        transition(mission_id, state, reason=data.get("problem") or data.get("manager_decision") or f"Manager execution state: {state}")
        changes = {"current_task_id": data.get("task_id"), "sprint": data.get("sprint", (get_mission(mission_id) or {}).get("sprint", 1))}
        update_mission(mission_id, **changes)
        record_event("mission_state", mission_id=mission_id, task_id=data.get("task_id"), data={"state": state, **data})
        if data.get("workers"):
            current = list((get_mission(mission_id) or {}).get("active_workers", []))
            for worker_id in data["workers"]:
                if worker_id and worker_id not in current:
                    current.append(worker_id)
            update_mission(mission_id, active_workers=current)

    try:
        result = run_mission(request, free_only=free_only, state_callback=sync_state)
        for task in result.tasks:
            add_task(mission_id, task.model_dump(mode="json"))
            if task.worker_id:
                current = list((get_mission(mission_id) or {}).get("active_workers", []))
                for worker_id in [task.worker_id, *task.collaborators]:
                    if worker_id and worker_id not in current:
                        current.append(worker_id)
                update_mission(mission_id, active_workers=current)
            record_event("task_execution", mission_id=mission_id, task_id=task.task_id, actor=task.worker_id or "nexus-manager", data={
                "status": task.status, "task_type": task.task_type, "worker_id": task.worker_id,
                "collaborators": task.collaborators, "candidate_worker_ids": task.candidate_worker_ids,
                "manager_confidence": task.manager_confidence, "manager_estimated_value": task.manager_estimated_value,
                "manager_resource_cost": task.manager_resource_cost, "sprint": task.sprint,
                "rework_number": task.rework_number, "error": task.error,
            })
            if task.manager_decision:
                decision = {"task_id": task.task_id, "decision": task.manager_decision, "worker_id": task.worker_id,
                            "candidates": task.candidate_worker_ids, "collaborators": task.collaborators,
                            "rationale": task.manager_rationale, "confidence": task.manager_confidence,
                            "estimated_value": task.manager_estimated_value, "resource_cost": task.manager_resource_cost}
                add_decision(mission_id, decision)
                decision_record(mission_id=mission_id, task_id=task.task_id, task_type=task.task_type,
                                selected_worker_id=task.worker_id, candidates=task.candidate_worker_ids,
                                decision=task.manager_decision, rationale=task.manager_rationale or "Mission execution decision",
                                confidence=task.manager_confidence or 0, expected_value=task.manager_estimated_value or 0,
                                resource_cost=task.manager_resource_cost or 0)
            if task.quality_decision:
                finding = {"task_id": task.task_id, "recommendation": task.quality_decision,
                           "problem": task.rework_problem, "quality_score": task.quality_score,
                           "rework_number": task.rework_number}
                add_qa_finding(mission_id, finding)
                record_event("qa_rework" if task.quality_decision == "REWORK" else "qa_pass",
                             mission_id=mission_id, task_id=task.task_id, actor=task.worker_id or "reviewer", data=finding)
            for artifact_id in task.artifact_ids:
                artifact = next((a for a in result.artifacts if a.artifact_id == artifact_id), None)
                if artifact:
                    add_artifact(mission_id, artifact.model_dump(mode="json"))
            if task.status in {"completed", "reviewed"}:
                record_resource_use(mission_id, int(max(1, round(task.manager_resource_cost or 1))))

        final_quality = next((task.quality_score for task in reversed(result.tasks) if task.quality_score is not None), None)
        final_review = next((task for task in reversed(result.tasks) if task.task_type == "quality_review" and task.status == "reviewed"), None)
        failed_tasks = [task for task in result.tasks if task.status in {"failed", "blocked"}]
        if result.status != "completed" and final_review and final_review.quality_decision == "PASS" and not failed_tasks and result.rework_count < result.max_reworks:
            result = result.model_copy(update={"status": "completed", "manager_decision": "ACCEPT"})
            record_event("mission_recovered_after_rework", mission_id=mission_id, data={"reason": "Final independent QA passed after rework.", "quality_score": final_quality, "rework_count": result.rework_count})

        final_state = "COMPLETED" if result.status == "completed" else ("REWORK_LIMIT_REACHED" if result.status == "rework_limit_reached" else "FAILED")
        transition(mission_id, final_state, reason=f"Mission result: {result.status}; final Manager decision: {result.manager_decision}")
        actual_resource_used = min(request.resource_budget, sum(int(max(1, round(t.manager_resource_cost or 1))) for t in result.tasks if t.status in {"completed", "reviewed"}))
        update_mission(mission_id, rework_count=result.rework_count, resource_used=actual_resource_used)
        record_event("manager_final_decision", mission_id=mission_id, data={"decision": result.manager_decision, "status": result.status, "quality_score": final_quality, "rework_count": result.rework_count})
        if result.status == "completed":
            complete_mission(mission_id, final_decision=result.manager_decision, final_quality=final_quality)
        else:
            record_event("mission_ended", mission_id=mission_id, data={"status": result.status, "manager_decision": result.manager_decision, "rework_count": result.rework_count, "final_quality": final_quality})
        return result
    except Exception as exc:
        transition(mission_id, "FAILED", reason=str(exc))
        record_event("mission_failed", mission_id=mission_id, data={"error": str(exc)})
        raise
