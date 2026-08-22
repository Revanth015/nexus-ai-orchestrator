from __future__ import annotations

import re
from typing import Callable
from pydantic import BaseModel, Field
from .ai_connectors import generate_claude, generate_perplexity
from .file_store import read_file
from .gemini_connector import generate_text
from .local_workers import execute_local_task
from .prompt_analyzer import analyze_prompt
from .task_planner import build_task_plan
from .worker_learning import record_result, task_performance
from .worker_router import route_task
from .manager_decision import decide as manager_decide


class ExecutionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    task_type: str = Field(default="general_reasoning", min_length=1, max_length=64)
    file_ids: list[str] = Field(default_factory=list, max_length=10)
    forced_worker_id: str | None = None
    excluded_worker_ids: list[str] = Field(default_factory=list, max_length=20)


class MissionExecutionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    file_ids: list[str] = Field(default_factory=list, max_length=10)
    resource_budget: int = Field(default=12, ge=1, le=100)


class ExecutionResponse(BaseModel):
    status: str
    task_type: str
    worker_id: str
    worker_name: str
    routing_policy: str
    route_score: float
    output: str
    telemetry: dict[str, object]


class ArtifactRecord(BaseModel):
    artifact_id: str
    task_id: str
    name: str
    artifact_type: str
    content: str
    size_chars: int
    preview: str


class TaskExecutionRecord(BaseModel):
    task_id: str
    task_type: str
    title: str
    status: str
    worker_id: str | None = None
    worker_name: str | None = None
    output: str | None = None
    route_score: float | None = None
    telemetry: dict[str, object] | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    collaborators: list[str] = Field(default_factory=list)
    candidate_worker_ids: list[str] = Field(default_factory=list)
    manager_confidence: float | None = None
    manager_estimated_value: float | None = None
    manager_resource_cost: float | None = None
    quality_decision: str | None = None
    quality_score: float | None = None
    review_recommendation: str | None = None
    manager_decision: str | None = None
    manager_rationale: str | None = None
    rework_number: int = 0
    rework_problem: str | None = None
    sprint: int = 1
    error: str | None = None


class MissionExecutionResponse(BaseModel):
    status: str
    objective: str
    execution_order: list[str]
    manager_decision: str
    rework_count: int
    max_reworks: int
    tasks: list[TaskExecutionRecord]
    artifacts: list[ArtifactRecord]


class ManagerExecutionDecision(BaseModel):
    action: str
    rationale: str
    confidence: float
    estimated_value: float
    resource_cost: float
    verification_required: bool
    collaboration_required: bool
    selected_worker_id: str | None = None
    collaborator_worker_ids: list[str] = Field(default_factory=list)
    candidate_worker_ids: list[str] = Field(default_factory=list)


_TASK_METRICS = {
    "research": (60, 45), "file_analysis": (55, 50), "data_analysis": (65, 55),
    "writing": (40, 35), "presentation": (70, 60), "image_generation": (55, 45),
    "coding": (70, 65), "quality_review": (80, 85), "general_reasoning": (45, 40),
}


def _task_complexity(task_type: str, prompt: str) -> float:
    base = _TASK_METRICS.get(task_type, (50, 50))[0]
    text = prompt.lower()
    signals = ("compare", "multiple", "strategy", "recommend", "critical", "verify", "sources", "complex", "integrate", "optimize")
    base += min(25, sum(word in text for word in signals) * 3)
    if len(prompt) > 1200:
        base += 10
    return min(100, base)


def _quality_risk(task_type: str, prompt: str) -> float:
    base = _TASK_METRICS.get(task_type, (50, 50))[1]
    text = prompt.lower()
    if any(x in text for x in ("financial", "medical", "legal", "safety", "critical", "ceo", "decision")):
        base += 15
    return min(100, base)


def decide_worker_for_task(
    task_type: str,
    *,
    prompt: str = "",
    free_only: bool = True,
    budget_remaining: int = 10,
    exclude_worker_ids: set[str] | None = None,
) -> ManagerExecutionDecision:
    route = route_task(task_type, free_only=free_only, exclude_worker_ids=exclude_worker_ids)
    candidates = [c for c in route.candidates if c.execution_ready and c.eligible_for_task]
    candidate_ids = [c.worker_id for c in candidates]
    if not candidates:
        return ManagerExecutionDecision(
            action="STOP",
            rationale=f"No execution-ready worker is available for {task_type} after applying Manager exclusions.",
            confidence=0, estimated_value=0, resource_cost=0,
            verification_required=False, collaboration_required=False,
            candidate_worker_ids=candidate_ids,
        )
    evidence = [(c, task_performance(c.worker_id, task_type)) for c in candidates]
    best, performance = max(
        evidence,
        key=lambda item: (item[1].get("score", 0), item[1].get("confidence", 0), item[0].score),
    )
    complexity = _task_complexity(task_type, prompt)
    quality_risk = _quality_risk(task_type, prompt)
    confidence = float(performance.get("confidence", 0))
    collaboration_score = 0.0
    if len(candidates) > 1:
        second = sorted(candidates, key=lambda c: c.score, reverse=True)[1]
        collaboration_score = max(
            0.0,
            min(100.0, 50.0 - abs(best.score - second.score) + second.capability_score * 0.5),
        )
    decision = manager_decide(
        task_type=task_type,
        complexity=complexity,
        confidence=confidence,
        quality_risk=quality_risk,
        worker_score=performance.get("score", 0),
        collaboration_score=collaboration_score,
        latency_ms=performance.get("avg_latency_ms", 0),
        budget_remaining=budget_remaining,
        evidence_gap=100 - confidence,
    )
    collaborator_ids: list[str] = []
    if decision.collaboration_required and len(candidates) > 1:
        collaborator_ids = [
            c.worker_id for c in sorted(candidates, key=lambda c: c.score, reverse=True)
            if c.worker_id != best.worker_id
        ][:1]
    return ManagerExecutionDecision(
        action=decision.action,
        rationale=decision.rationale,
        confidence=decision.confidence,
        estimated_value=decision.estimated_value,
        resource_cost=decision.resource_cost,
        verification_required=decision.verification_required,
        collaboration_required=decision.collaboration_required,
        selected_worker_id=None if decision.action == "STOP" else best.worker_id,
        collaborator_worker_ids=collaborator_ids,
        candidate_worker_ids=candidate_ids,
    )


def _load_files(file_ids):
    if len(file_ids) > 10:
        raise ValueError("A maximum of 10 files can be supplied to one execution.")
    return [read_file(file_id) for file_id in file_ids]


def _file_context_text(files):
    return "\n\n".join(
        f"FILE: {item.get('filename', item.get('file_id', 'unknown'))}\nTYPE: {item.get('extension', '')}\nEXTRACTED CONTENT:\n{str(item.get('content', ''))[:12000]}"
        for item in files
    )


def _run_worker(worker_id, task_type, prompt, files):
    if worker_id == "gemini":
        return generate_text(prompt)
    if worker_id == "claude":
        return generate_claude(prompt)
    if worker_id == "perplexity":
        return generate_perplexity(prompt)
    if worker_id in {"local-tools", "local-validator"}:
        return execute_local_task(task_type, prompt, file_context=files)
    raise RuntimeError(f"Worker '{worker_id}' has no registered executor.")


def execute_task(request: ExecutionRequest, *, free_only=True) -> ExecutionResponse:
    route = route_task(
        request.task_type,
        free_only=free_only,
        exclude_worker_ids=set(request.excluded_worker_ids),
    )
    if request.forced_worker_id:
        candidate = next(
            (
                item for item in route.candidates
                if item.worker_id == request.forced_worker_id
                and item.execution_ready
                and item.eligible_for_task
            ),
            None,
        )
        if candidate is None:
            raise RuntimeError(
                f"Manager selected worker '{request.forced_worker_id}', but that worker is not execution-ready, eligible, or allowed for this task."
            )
        routing_policy = "manager_directed_allocation"
    else:
        if not route.execution_ready or not route.recommended_worker_id:
            raise RuntimeError(f"No execution-ready free worker is available for task type '{request.task_type}'.")
        candidate = next(
            (
                item for item in route.candidates
                if item.worker_id == route.recommended_worker_id
                and item.execution_ready
                and item.eligible_for_task
            ),
            None,
        )
        if candidate is None:
            raise RuntimeError(f"Worker routing selected '{route.recommended_worker_id}', but that worker is not execution-ready or eligible.")
        routing_policy = route.routing_policy
    files = _load_files(request.file_ids)
    prompt = request.prompt + ("\n\nUploaded file context:\n" + _file_context_text(files) if files else "")
    try:
        result = _run_worker(candidate.worker_id, request.task_type, prompt, files)
    except Exception:
        record_result(candidate.worker_id, task_type=request.task_type, success=False)
        raise
    telemetry = result["telemetry"]
    record_result(
        candidate.worker_id,
        task_type=request.task_type,
        success=True,
        latency_ms=float(telemetry.get("last_latency_ms") or 0),
    )
    return ExecutionResponse(
        status="completed",
        task_type=request.task_type,
        worker_id=candidate.worker_id,
        worker_name=candidate.name,
        routing_policy=routing_policy,
        route_score=candidate.score,
        output=str(result["text"]),
        telemetry=telemetry,
    )


def _task_prompt(objective, title, task_type, inputs, artifacts, feedback=None):
    context = ""
    if inputs:
        supplied = [f"{name}: {artifacts[name]}" for name in inputs if name in artifacts]
        if supplied:
            context = "\n\nPrevious task outputs:\n" + "\n\n".join(supplied)
    feedback_text = f"\n\nQA problem to fix:\n{feedback}" if feedback else ""
    role = ""
    if task_type == "quality_review":
        role = (
            "\n\nReview the upstream employee output independently for factual accuracy, completeness, relevance, "
            "structure, consistency, and compliance. Do not make the final acceptance decision. End exactly with: "
            "Quality score: <0-100>\nProblem identified: <specific problem or None identified.>\n"
            "Recommendation to NEXUS Manager: <PASS or REWORK>."
        )
    return f"Mission objective:\n{objective}\n\nCurrent task: {title}\nTask type: {task_type}\nComplete only this task and produce a concise artifact for downstream employees.{role}{context}{feedback_text}"


def _artifact_type(task_type):
    return {
        "research": "research_brief", "file_analysis": "file_analysis", "data_analysis": "analysis_findings",
        "presentation": "presentation_draft", "quality_review": "quality_review", "writing": "written_draft",
        "image_generation": "image_output", "coding": "code_output", "general_reasoning": "reasoning_output",
    }.get(task_type, "task_output")


def _review_recommendation(output):
    match = re.search(r"Recommendation to NEXUS Manager:\s*(PASS|REWORK)", output, re.I)
    if match:
        return match.group(1).upper()
    return next((line.strip().upper() for line in reversed(output.splitlines()) if line.strip().upper() in {"PASS", "REWORK"}), None)


def _review_problem(output):
    match = re.search(r"Problem identified:\s*(.+)", output, re.I)
    return match.group(1).strip() if match else None


def _quality_score(output):
    match = re.search(r"Quality score:\s*(\d+(?:\.\d+)?)", output, re.I)
    return max(0.0, min(100.0, float(match.group(1)))) if match else None


def _mission_response(status, plan, execution_order, manager_decision, rework_count, records, artifacts):
    return MissionExecutionResponse(
        status=status,
        objective=plan.objective,
        execution_order=execution_order,
        manager_decision=manager_decision,
        rework_count=rework_count,
        max_reworks=3,
        tasks=records,
        artifacts=artifacts,
    )


def execute_mission(request: MissionExecutionRequest, *, free_only=True, state_callback: Callable[[str, dict], None] | None = None) -> MissionExecutionResponse:
    analysis = analyze_prompt(request.prompt)
    plan = build_task_plan(analysis)
    artifacts_by_name = {}
    rework_feedback_by_task = {}
    artifact_records = []
    records = []
    execution_order = list(plan.execution_order)
    task_by_id = {t.task_id: t for t in plan.tasks}
    rework_count = 0
    max_reworks = 3
    resource_budget = request.resource_budget
    resource_used = 0.0
    index = 0

    if state_callback:
        state_callback("ALLOCATING", {"objective": plan.objective, "task_count": len(plan.tasks), "sprint": 1})

    while index < len(execution_order):
        task = task_by_id[execution_order[index]]
        if state_callback:
            state_callback(
                "REVIEWING" if task.task_type == "quality_review" else "EXECUTING",
                {"task_id": task.task_id, "task_type": task.task_type, "sprint": task.sprint},
            )
        missing = [
            dep for dep in task.dependencies
            if not any(r.task_id == dep and r.status in {"completed", "reviewed"} for r in records)
        ]
        if missing:
            records.append(
                TaskExecutionRecord(
                    task_id=task.task_id, task_type=task.task_type, title=task.title,
                    status="blocked", sprint=task.sprint,
                    error=f"Dependencies not completed: {', '.join(missing)}",
                )
            )
            break

        try:
            feedback = rework_feedback_by_task.get(task.task_id)
            is_review = task.task_type == "quality_review"
            excluded = {r.worker_id for r in records if r.worker_id} if is_review else set()
            task_prompt = _task_prompt(plan.objective, task.title, task.task_type, task.inputs, artifacts_by_name, feedback)
            budget_remaining = int(max(0, resource_budget - resource_used))
            manager_allocation = decide_worker_for_task(
                task.task_type,
                prompt=task_prompt,
                free_only=free_only,
                budget_remaining=budget_remaining,
                exclude_worker_ids=excluded,
            )
            if manager_allocation.action == "STOP" or not manager_allocation.selected_worker_id:
                raise RuntimeError(f"Manager stopped task '{task.title}': {manager_allocation.rationale}")
            planned_cost = manager_allocation.resource_cost
            if resource_used + planned_cost > resource_budget:
                raise RuntimeError(
                    f"Resource budget exhausted for task '{task.title}'. Required {planned_cost:.1f}, remaining {resource_budget - resource_used:.1f}."
                )
            if state_callback:
                state_callback(
                    "ALLOCATING",
                    {
                        "task_id": task.task_id,
                        "manager_decision": manager_allocation.action,
                        "selected_worker": manager_allocation.selected_worker_id,
                        "candidates": manager_allocation.candidate_worker_ids,
                        "rationale": manager_allocation.rationale,
                        "confidence": manager_allocation.confidence,
                        "estimated_value": manager_allocation.estimated_value,
                        "resource_cost": planned_cost,
                    },
                )

            if manager_allocation.collaboration_required and manager_allocation.collaborator_worker_ids:
                if state_callback:
                    state_callback(
                        "COLLABORATING",
                        {"task_id": task.task_id, "workers": [manager_allocation.selected_worker_id, *manager_allocation.collaborator_worker_ids]},
                    )

            execution = execute_task(
                ExecutionRequest(
                    task_type=task.task_type,
                    prompt=task_prompt,
                    file_ids=request.file_ids,
                    forced_worker_id=manager_allocation.selected_worker_id,
                    excluded_worker_ids=list(excluded),
                ),
                free_only=free_only,
            )
            resource_used += 1

            collaborator_outputs = []
            for collaborator_id in manager_allocation.collaborator_worker_ids:
                if collaborator_id in excluded or collaborator_id == execution.worker_id:
                    continue
                collab_prompt = (
                    _task_prompt(plan.objective, f"Collaborative perspective for: {task.title}", task.task_type, task.inputs, artifacts_by_name, feedback)
                    + "\n\nYou are a collaborating employee. Provide an independent perspective that the primary employee can use. Do not make the final Manager decision."
                )
                collab = execute_task(
                    ExecutionRequest(
                        task_type=task.task_type,
                        prompt=collab_prompt,
                        file_ids=request.file_ids,
                        forced_worker_id=collaborator_id,
                        excluded_worker_ids=list(excluded),
                    ),
                    free_only=free_only,
                )
                resource_used += 1
                collaborator_outputs.append(collab.output)

            combined_output = execution.output
            if collaborator_outputs:
                combined_output += "\n\n--- COLLABORATOR INPUT ---\n" + "\n\n".join(collaborator_outputs)
            artifact_ids = []
            for output_name in task.outputs:
                artifact_id = f"{task.task_id}:{output_name}"
                content = combined_output
                artifact_records.append(
                    ArtifactRecord(
                        artifact_id=artifact_id, task_id=task.task_id, name=output_name,
                        artifact_type=_artifact_type(task.task_type), content=content,
                        size_chars=len(content), preview=content[:280].replace("\n", " "),
                    )
                )
                artifacts_by_name[output_name] = content
                artifact_ids.append(artifact_id)

            base_record = dict(
                task_id=task.task_id, task_type=task.task_type, title=task.title,
                worker_id=execution.worker_id, worker_name=execution.worker_name,
                output=combined_output, route_score=execution.route_score,
                telemetry=execution.telemetry, artifact_ids=artifact_ids,
                collaborators=manager_allocation.collaborator_worker_ids,
                candidate_worker_ids=manager_allocation.candidate_worker_ids,
                manager_confidence=manager_allocation.confidence,
                manager_estimated_value=manager_allocation.estimated_value,
                manager_resource_cost=planned_cost,
                manager_decision=manager_allocation.action,
                manager_rationale=manager_allocation.rationale,
                sprint=task.sprint,
            )

            if task.quality_gate:
                recommendation = _review_recommendation(execution.output) or "REWORK"
                problem = _review_problem(execution.output)
                quality_score = _quality_score(execution.output)
                manager_decision = "ACCEPT" if recommendation == "PASS" else "REWORK"
                record_result(
                    execution.worker_id,
                    task_type="quality_review",
                    success=True,
                    latency_ms=float(execution.telemetry.get("last_latency_ms") or 0),
                    quality=recommendation,
                )
                records.append(
                    TaskExecutionRecord(
                        status="reviewed", quality_decision=recommendation,
                        quality_score=quality_score, review_recommendation=recommendation,
                        manager_decision=manager_decision, rework_number=rework_count,
                        rework_problem=problem, **base_record,
                    )
                )
                if manager_decision == "REWORK":
                    if rework_count >= max_reworks:
                        if state_callback:
                            state_callback("REWORK_LIMIT_REACHED", {"task_id": task.task_id, "problem": problem, "rework_count": rework_count})
                        return _mission_response("rework_limit_reached", plan, execution_order, "REWORK", rework_count, records, artifact_records)
                    target = next((r for r in reversed(records[:-1]) if r.status == "completed" and r.task_type != "quality_review"), None)
                    if target is None:
                        return _mission_response("rework_required", plan, execution_order, "REWORK", rework_count, records, artifact_records)
                    rework_count += 1
                    if state_callback:
                        state_callback("REWORKING", {"task_id": target.task_id, "rework_number": rework_count, "problem": problem})
                    target_task = task_by_id[target.task_id]
                    rework_id = f"{target.task_id}_rework_{rework_count}"
                    rework_task = target_task.model_copy(
                        update={
                            "task_id": rework_id,
                            "title": f"Rework #{rework_count}: {target.title}",
                            "dependencies": [task.task_id],
                            "inputs": list(target_task.outputs),
                            "quality_gate": False,
                            "outputs": [f"{target.task_type}_rework_{rework_count}"],
                            "sprint": task.sprint + 1,
                        }
                    )
                    task_by_id[rework_id] = rework_task
                    rework_feedback_by_task[rework_id] = problem or "Correct the reviewed work using independent inspection."
                    execution_order.insert(index + 1, rework_id)
                    review_id = f"quality_review_{rework_count}"
                    review_task = task_by_id[task.task_id].model_copy(
                        update={
                            "task_id": review_id,
                            "title": f"Review rework #{rework_count}",
                            "dependencies": [rework_id],
                            "inputs": list(rework_task.outputs),
                            "outputs": [f"quality_review_{rework_count}"],
                            "sprint": task.sprint + 1,
                        }
                    )
                    task_by_id[review_id] = review_task
                    execution_order.insert(index + 2, review_id)
                index += 1
                continue

            records.append(TaskExecutionRecord(status="completed", **base_record))

            # A Manager verification decision is a real downstream QA employee, not just a flag.
            if manager_allocation.verification_required and not is_review:
                review_id = f"manager_verify_{task.task_id}"
                review_task = task.model_copy(
                    update={
                        "task_id": review_id,
                        "title": f"Independent Manager verification: {task.title}",
                        "task_type": "quality_review",
                        "dependencies": [task.task_id],
                        "inputs": list(task.outputs),
                        "outputs": [f"manager_verification_{task.task_id}"],
                        "quality_gate": True,
                        "sprint": task.sprint,
                    }
                )
                task_by_id[review_id] = review_task
                execution_order.insert(index + 1, review_id)

        except Exception as exc:
            records.append(
                TaskExecutionRecord(
                    task_id=task.task_id, task_type=task.task_type, title=task.title,
                    status="failed", sprint=task.sprint, error=str(exc), manager_decision="STOP",
                )
            )
            if state_callback:
                state_callback("FAILED", {"task_id": task.task_id, "error": str(exc)})
            break
        index += 1

    successful_records = [r for r in records if r.status in {"completed", "reviewed"}]
    failed_records = [r for r in records if r.status in {"failed", "blocked"}]
    review_records = [r for r in records if r.task_type == "quality_review" and r.status == "reviewed"]
    final_quality = next((r.quality_score for r in reversed(review_records) if r.quality_score is not None), None)
    all_reviews_passed = bool(review_records) and all(r.quality_decision == "PASS" for r in review_records)
    no_failures = not failed_records
    manager_decision = "ACCEPT" if successful_records and no_failures and (all_reviews_passed or not review_records) else "REJECT"
    status = "completed" if manager_decision == "ACCEPT" else ("rework_limit_reached" if rework_count >= max_reworks else "failed")
    if state_callback:
        state_callback(
            "MANAGER_REVIEW",
            {
                "manager_decision": manager_decision,
                "quality_score": final_quality,
                "rework_count": rework_count,
                "resource_used": resource_used,
                "resource_budget": resource_budget,
            },
        )
    return _mission_response(status, plan, execution_order, manager_decision, rework_count, records, artifact_records)
