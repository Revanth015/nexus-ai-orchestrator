from __future__ import annotations

import json
import re
from typing import Any, Callable
from pydantic import BaseModel, Field
from .files_service import read_file
from .local_workers import execute_local_task
from .manager_decision import manager_decide
from .planner import analyze_prompt, build_task_plan
from .providers import generate_claude, generate_perplexity, generate_text
from .router import route_task
from .worker_registry import record_result, task_performance
from .ai_connections import generate_custom

_TASK_METRICS = {"research": (65, 55), "file_analysis": (60, 60), "data_analysis": (70, 65), "presentation": (55, 50), "quality_review": (60, 75), "writing": (45, 45), "image_generation": (40, 35), "coding": (75, 70), "general_reasoning": (50, 55)}

class ExecutionRequest(BaseModel):
    task_type: str
    prompt: str
    file_ids: list[str] = Field(default_factory=list)
    forced_worker_id: str | None = None
    excluded_worker_ids: list[str] = Field(default_factory=list)
    allow_fallback: bool = True

class ExecutionResponse(BaseModel):
    status: str
    task_type: str
    worker_id: str
    worker_name: str
    routing_policy: str
    route_score: float
    output: str
    telemetry: dict
    attempts: int = 1
    fallback_used: bool = False
    failed_worker_ids: list[str] = Field(default_factory=list)

class MissionExecutionRequest(BaseModel):
    prompt: str
    file_ids: list[str] = Field(default_factory=list)
    resource_budget: int = Field(default=12, ge=1, le=100)

class ArtifactRecord(BaseModel):
    artifact_id: str
    task_id: str
    name: str
    artifact_type: str
    content: str
    size_chars: int
    preview: str
    version: int = 1
    source_task_id: str

class TaskExecutionRecord(BaseModel):
    task_id: str
    task_type: str
    title: str
    status: str
    worker_id: str | None = None
    worker_name: str | None = None
    output: str | None = None
    route_score: float | None = None
    telemetry: dict = Field(default_factory=dict)
    artifact_ids: list[str] = Field(default_factory=list)
    collaborators: list[str] = Field(default_factory=list)
    candidate_worker_ids: list[str] = Field(default_factory=list)
    failed_worker_ids: list[str] = Field(default_factory=list)
    manager_confidence: float | None = None
    manager_estimated_value: float | None = None
    manager_resource_cost: float | None = None
    actual_resource_cost: float = 0.0
    manager_decision: str | None = None
    manager_rationale: str | None = None
    quality_decision: str | None = None
    quality_score: float | None = None
    review_recommendation: str | None = None
    review_worker_id: str | None = None
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
    resource_used: float = 0.0
    resource_budget: int = 12
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


def _task_complexity(task_type: str, prompt: str) -> float:
    base = _TASK_METRICS.get(task_type, (50, 50))[0]
    bonus = min(20, len(prompt) / 500)
    if any(x in prompt.lower() for x in ("multiple", "compare", "optimize", "strategy", "integrate", "forecast")): bonus += 10
    return min(100, base + bonus)


def _quality_risk(task_type: str, prompt: str) -> float:
    base = _TASK_METRICS.get(task_type, (50, 50))[1]
    if any(x in prompt.lower() for x in ("financial", "medical", "legal", "safety", "critical", "ceo", "decision")): base += 15
    return min(100, base)


def decide_worker_for_task(task_type: str, *, prompt: str = "", free_only: bool = True, budget_remaining: int = 10, exclude_worker_ids: set[str] | None = None) -> ManagerExecutionDecision:
    route = route_task(task_type, free_only=free_only, exclude_worker_ids=exclude_worker_ids)
    candidates = [c for c in route.candidates if c.execution_ready and c.eligible_for_task]
    ids = [c.worker_id for c in candidates]
    if not candidates:
        return ManagerExecutionDecision(action="STOP", rationale=f"No execution-ready worker is available for {task_type} after applying Manager exclusions.", confidence=0, estimated_value=0, resource_cost=0, verification_required=False, collaboration_required=False, candidate_worker_ids=ids)
    evidence = [(c, task_performance(c.worker_id, task_type)) for c in candidates]
    best, performance = max(evidence, key=lambda item: (item[1].get("score", 0), item[1].get("confidence", 0), item[0].score))
    complexity = _task_complexity(task_type, prompt); risk = _quality_risk(task_type, prompt); confidence = float(performance.get("confidence", 0)); collaboration_score = 0.0
    if len(candidates) > 1:
        second = sorted(candidates, key=lambda c: c.score, reverse=True)[1]
        collaboration_score = max(0.0, min(100.0, 50.0 - abs(best.score - second.score) + second.capability_score * 0.5))
    decision = manager_decide(task_type=task_type, complexity=complexity, confidence=confidence, quality_risk=risk, worker_score=performance.get("score", 0), collaboration_score=collaboration_score, latency_ms=performance.get("avg_latency_ms", 0), budget_remaining=budget_remaining, evidence_gap=100-confidence)
    collaborators = []
    if decision.collaboration_required and len(candidates) > 1: collaborators = [c.worker_id for c in sorted(candidates, key=lambda c: c.score, reverse=True) if c.worker_id != best.worker_id][:1]
    return ManagerExecutionDecision(action=decision.action, rationale=decision.rationale, confidence=decision.confidence, estimated_value=decision.estimated_value, resource_cost=decision.resource_cost, verification_required=decision.verification_required, collaboration_required=decision.collaboration_required, selected_worker_id=None if decision.action == "STOP" else best.worker_id, collaborator_worker_ids=collaborators, candidate_worker_ids=ids)


def _load_files(file_ids: list[str]) -> list[dict[str, object]]:
    if len(file_ids) > 10: raise ValueError("A maximum of 10 files can be supplied to one execution.")
    return [read_file(x) for x in file_ids]


def _file_context_text(files: list[dict[str, object]]) -> str:
    return "\n\n".join(f"FILE: {x.get('filename', x.get('file_id', 'unknown'))}\nTYPE: {x.get('extension', '')}\nEXTRACTED CONTENT:\n{str(x.get('content', ''))[:12000]}" for x in files)


def _run_worker(worker_id: str, task_type: str, prompt: str, files: list[dict[str, object]]) -> dict[str, Any]:
    if worker_id == "gemini": return generate_text(prompt)
    if worker_id == "claude": return generate_claude(prompt)
    if worker_id == "perplexity": return generate_perplexity(prompt)
    if worker_id in {"local-tools", "local-validator"}: return execute_local_task(task_type, prompt, file_context=files)
    if worker_id.startswith("custom-"): return generate_custom(worker_id, prompt)
    raise RuntimeError(f"Worker '{worker_id}' has no registered executor.")


def execute_task(request: ExecutionRequest, *, free_only: bool = True) -> ExecutionResponse:
    files = _load_files(request.file_ids)
    prompt = request.prompt + ("\n\nUploaded file context:\n" + _file_context_text(files) if files else "")
    excluded = set(request.excluded_worker_ids); attempts = 0; failed: list[str] = []; forced = request.forced_worker_id
    while attempts < 10:
        attempts += 1
        route = route_task(request.task_type, free_only=free_only, exclude_worker_ids=excluded)
        if forced:
            candidate = next((x for x in route.candidates if x.worker_id == forced and x.execution_ready and x.eligible_for_task), None)
            if candidate is None:
                if attempts == 1: raise RuntimeError(f"Manager selected worker '{forced}', but that worker is not execution-ready, eligible, or allowed for this task.")
                forced = None; continue
            policy = "manager_directed_allocation" if attempts == 1 else "manager_fallback_allocation"
        else:
            candidate = next((x for x in route.candidates if x.worker_id == route.recommended_worker_id and x.execution_ready and x.eligible_for_task), None)
            if candidate is None: raise RuntimeError(f"No execution-ready worker is available for task type '{request.task_type}'.")
            policy = route.routing_policy if attempts == 1 else "automatic_failover"
        try:
            result = _run_worker(candidate.worker_id, request.task_type, prompt, files)
            telemetry = result.get("telemetry", {}); latency = float(telemetry.get("last_latency_ms") or result.get("latency_ms") or 0)
            record_result(candidate.worker_id, task_type=request.task_type, success=True, latency_ms=latency)
            return ExecutionResponse(status="completed", task_type=request.task_type, worker_id=candidate.worker_id, worker_name=candidate.name, routing_policy=policy, route_score=candidate.score, output=str(result.get("text", "")), telemetry=telemetry, attempts=attempts, fallback_used=bool(failed), failed_worker_ids=failed)
        except Exception as exc:
            failed.append(candidate.worker_id); excluded.add(candidate.worker_id); record_result(candidate.worker_id, task_type=request.task_type, success=False)
            if not request.allow_fallback: raise
            remaining = route_task(request.task_type, free_only=free_only, exclude_worker_ids=excluded)
            if not any(c.execution_ready and c.eligible_for_task for c in remaining.candidates):
                raise RuntimeError(f"Worker '{candidate.worker_id}' failed and no safe fallback worker is available for {request.task_type}: {exc}") from exc
            forced = None
    raise RuntimeError(f"Execution exhausted failover attempts for task type '{request.task_type}'.")


def _task_prompt(objective: str, title: str, task_type: str, inputs: list[str], artifacts: dict[str, str], feedback: str | None = None) -> str:
    supplied = [f"{name}: {artifacts[name]}" for name in inputs if name in artifacts]
    context = "\n\nPrevious task outputs:\n" + "\n\n".join(supplied) if supplied else ""
    feedback_text = f"\n\nQA problem to fix:\n{feedback}" if feedback else ""
    return f"Mission objective:\n{objective}\n\nCurrent task: {title}\nTask type: {task_type}\nComplete only this task and produce a concise artifact for downstream employees.{context}{feedback_text}"


def _review_prompt(objective: str, task_id: str, task_title: str, output: str) -> str:
    return f'''You are an independent NEXUS QA employee. You did not produce this work. Review only the supplied artifact for factual accuracy, completeness, relevance, structure, consistency and instruction compliance.

Mission objective: {objective}
Target task ID: {task_id}
Target task title: {task_title}

ARTIFACT TO REVIEW:
{output[:30000]}

Return JSON only: {{"quality_score": 0, "decision": "PASS", "problem": "None identified.", "severity": "none"}}
Use PASS only when the artifact is acceptable. Use REWORK when a material issue should be corrected. Never make the corporate Manager acceptance decision.'''


def _parse_review(output: str) -> tuple[str, float | None, str | None, str | None]:
    try:
        match = re.search(r"\{.*\}", output, re.S)
        if match:
            data = json.loads(match.group(0)); decision = str(data.get("decision", "")).upper()
            if decision in {"PASS", "REWORK"}:
                score = float(data["quality_score"]) if data.get("quality_score") is not None else None
                return decision, max(0, min(100, score)) if score is not None else None, str(data.get("problem") or "None identified."), str(data.get("severity") or "unknown")
    except (ValueError, TypeError, json.JSONDecodeError): pass
    recommendation = _review_recommendation(output) or "REWORK"
    return recommendation, _quality_score(output), _review_problem(output) or "QA response did not contain a valid structured review.", "unknown"


def _review_recommendation(output: str) -> str | None:
    m = re.search(r"Recommendation to NEXUS Manager:\s*(PASS|REWORK)", output, re.I)
    return m.group(1).upper() if m else next((x.strip().upper() for x in reversed(output.splitlines()) if x.strip().upper() in {"PASS", "REWORK"}), None)


def _review_problem(output: str) -> str | None:
    m = re.search(r"Problem identified:\s*(.+)", output, re.I); return m.group(1).strip() if m else None


def _quality_score(output: str) -> float | None:
    m = re.search(r"Quality score:\s*(\d+(?:\.\d+)?)", output, re.I); return max(0, min(100, float(m.group(1)))) if m else None


def _artifact_type(task_type: str) -> str:
    return {"research":"research_brief", "file_analysis":"file_analysis", "data_analysis":"analysis_findings", "presentation":"presentation_draft", "quality_review":"quality_review", "writing":"written_draft", "image_generation":"image_output", "coding":"code_output", "general_reasoning":"reasoning_output"}.get(task_type, "task_output")


def _mission_response(status: str, plan, execution_order: list[str], manager_decision: str, rework_count: int, records: list[TaskExecutionRecord], artifacts: list[ArtifactRecord], resource_used: float, resource_budget: int) -> MissionExecutionResponse:
    return MissionExecutionResponse(status=status, objective=plan.objective, execution_order=execution_order, manager_decision=manager_decision, rework_count=rework_count, max_reworks=3, resource_used=round(resource_used, 2), resource_budget=resource_budget, tasks=records, artifacts=artifacts)


def _run_independent_review(objective: str, target: TaskExecutionRecord, *, free_only: bool, excluded: set[str], file_ids: list[str]):
    review_route = route_task("quality_review", free_only=free_only, exclude_worker_ids=excluded)
    reviewer = next((c for c in review_route.candidates if c.execution_ready and c.eligible_for_task), None)
    if reviewer is None: raise RuntimeError("Independent verification was required but no independent QA worker is available.")
    review = execute_task(ExecutionRequest(task_type="quality_review", prompt=_review_prompt(objective, target.task_id, target.title, target.output or ""), file_ids=file_ids, forced_worker_id=reviewer.worker_id, excluded_worker_ids=list(excluded), allow_fallback=True), free_only=free_only)
    decision, score, problem, severity = _parse_review(review.output)
    return decision, score, problem, severity, review.worker_id, review.output, review.attempts


def _make_rework_task(task, review_task_id: str, number: int, sprint: int):
    return task.model_copy(update={"task_id": f"{task.task_id}_rework_{number}", "title": f"Rework #{number}: {task.title}", "dependencies": [review_task_id], "inputs": list(task.outputs), "quality_gate": False, "outputs": list(task.outputs), "sprint": sprint})


def execute_mission(request: MissionExecutionRequest, *, free_only: bool = True, state_callback: Callable[[str, dict], None] | None = None) -> MissionExecutionResponse:
    analysis = analyze_prompt(request.prompt); plan = build_task_plan(analysis)
    artifacts_by_name: dict[str, str] = {}; artifact_records: list[ArtifactRecord] = []; records: list[TaskExecutionRecord] = []
    execution_order = list(plan.execution_order); task_by_id = {t.task_id: t for t in plan.tasks}; rework_count = 0; resource_used = 0.0; index = 0; sprint = 1
    if not execution_order: return _mission_response("completed", plan, execution_order, "ACCEPT", 0, records, artifact_records, 0, request.resource_budget)
    if state_callback: state_callback("ALLOCATING", {"objective": plan.objective, "task_count": len(plan.tasks), "sprint": sprint})

    while index < len(execution_order):
        task = task_by_id[execution_order[index]]
        if state_callback: state_callback("REVIEWING" if task.task_type == "quality_review" else "EXECUTING", {"task_id": task.task_id, "task_type": task.task_type, "sprint": sprint})
        missing = [d for d in task.dependencies if not any(r.task_id == d and r.status in {"completed", "reviewed"} for r in records)]
        if missing:
            records.append(TaskExecutionRecord(task_id=task.task_id, task_type=task.task_type, title=task.title, status="blocked", sprint=sprint, error=f"Dependencies not completed: {', '.join(missing)}"))
            return _mission_response("failed", plan, execution_order, "REJECT", rework_count, records, artifact_records, resource_used, request.resource_budget)
        try:
            feedback = task.title if "_rework_" in task.task_id else None
            task_prompt = _task_prompt(plan.objective, task.title, task.task_type, task.inputs, artifacts_by_name, feedback)
            is_review = task.task_type == "quality_review"
            excluded = {r.worker_id for r in records if r.worker_id} if is_review else set()
            budget_remaining = int(max(0, request.resource_budget - resource_used))
            allocation = decide_worker_for_task(task.task_type, prompt=task_prompt, free_only=free_only, budget_remaining=budget_remaining, exclude_worker_ids=excluded)
            if allocation.action == "STOP" or not allocation.selected_worker_id:
                records.append(TaskExecutionRecord(task_id=task.task_id, task_type=task.task_type, title=task.title, status="failed", sprint=sprint, manager_decision=allocation.action, manager_rationale=allocation.rationale, candidate_worker_ids=allocation.candidate_worker_ids, error=allocation.rationale))
                return _mission_response("failed", plan, execution_order, "REJECT", rework_count, records, artifact_records, resource_used, request.resource_budget)
            planned_calls = 1 + len(allocation.collaborator_worker_ids) + (1 if allocation.verification_required and not is_review else 0)
            if resource_used + planned_calls > request.resource_budget:
                records.append(TaskExecutionRecord(task_id=task.task_id, task_type=task.task_type, title=task.title, status="failed", sprint=sprint, manager_decision="STOP", manager_rationale="Resource budget is insufficient for the selected execution and verification plan.", candidate_worker_ids=allocation.candidate_worker_ids, manager_resource_cost=float(planned_calls), error="Resource budget exhausted before execution."))
                return _mission_response("resource_exhausted", plan, execution_order, "STOP", rework_count, records, artifact_records, resource_used, request.resource_budget)

            execution = execute_task(ExecutionRequest(task_type=task.task_type, prompt=task_prompt, file_ids=request.file_ids, forced_worker_id=allocation.selected_worker_id, excluded_worker_ids=list(excluded), allow_fallback=True), free_only=free_only)
            resource_used += execution.attempts
            collaborator_outputs: list[str] = []; collaborator_ids: list[str] = []
            for collaborator_id in allocation.collaborator_worker_ids:
                if collaborator_id in excluded or collaborator_id == execution.worker_id: continue
                collab = execute_task(ExecutionRequest(task_type=task.task_type, prompt=task_prompt + "\n\nProvide an independent collaborating perspective.", file_ids=request.file_ids, forced_worker_id=collaborator_id, excluded_worker_ids=list(excluded), allow_fallback=True), free_only=free_only)
                resource_used += collab.attempts; collaborator_outputs.append(collab.output); collaborator_ids.append(collab.worker_id)
            combined = execution.output + (("\n\n--- COLLABORATOR INPUT ---\n" + "\n\n".join(collaborator_outputs)) if collaborator_outputs else "")
            artifact_ids: list[str] = []
            for output_name in task.outputs:
                artifact_id = f"{task.task_id}:{output_name}:v1"
                artifact = ArtifactRecord(artifact_id=artifact_id, task_id=task.task_id, name=output_name, artifact_type=_artifact_type(task.task_type), content=combined, size_chars=len(combined), preview=combined[:280].replace("\n", " "), version=1, source_task_id=task.task_id)
                artifact_records.append(artifact); artifacts_by_name[output_name] = combined; artifact_ids.append(artifact_id)
            record = TaskExecutionRecord(task_id=task.task_id, task_type=task.task_type, title=task.title, status="completed", worker_id=execution.worker_id, worker_name=execution.worker_name, output=combined, route_score=execution.route_score, telemetry=execution.telemetry, artifact_ids=artifact_ids, collaborators=collaborator_ids, candidate_worker_ids=allocation.candidate_worker_ids, failed_worker_ids=execution.failed_worker_ids, manager_confidence=allocation.confidence, manager_estimated_value=allocation.estimated_value, manager_resource_cost=float(planned_calls), actual_resource_cost=float(execution.attempts + len(collaborator_outputs)), manager_decision=allocation.action, manager_rationale=allocation.rationale, sprint=sprint)

            if is_review:
                decision, score, problem, severity = _parse_review(execution.output)
                record.status = "reviewed"; record.quality_decision = decision; record.quality_score = score; record.review_recommendation = decision; record.review_worker_id = execution.worker_id; record.rework_number = rework_count; record.rework_problem = problem if decision == "REWORK" else None
                records.append(record); record_result(execution.worker_id, task_type="quality_review", success=True, latency_ms=float(execution.telemetry.get("last_latency_ms") or 0), quality=decision, quality_score=score)
                if decision == "REWORK":
                    if rework_count >= 3: return _mission_response("rework_limit_reached", plan, execution_order, "REJECT", rework_count, records, artifact_records, resource_used, request.resource_budget)
                    target = next((r for r in reversed(records[:-1]) if r.status == "completed" and r.task_type != "quality_review"), None)
                    if target is None: return _mission_response("failed", plan, execution_order, "REJECT", rework_count, records, artifact_records, resource_used, request.resource_budget)
                    rework_count += 1; sprint += 1
                    target_task = task_by_id[target.task_id]; rework_task = _make_rework_task(target_task, task.task_id, rework_count, sprint); task_by_id[rework_task.task_id] = rework_task
                    review_id = f"quality_review_rework_{rework_count}"; review_task = task.model_copy(update={"task_id": review_id, "title": f"Independent QA for rework #{rework_count}", "dependencies": [rework_task.task_id], "inputs": list(target_task.outputs), "outputs": [f"quality_review_{rework_count}"], "sprint": sprint}); task_by_id[review_id] = review_task
                    execution_order[index:index + 1] = [rework_task.task_id, review_id]
                    index += 1; continue
                index += 1; continue

            if allocation.verification_required:
                decision, score, problem, severity, reviewer_id, _, review_attempts = _run_independent_review(plan.objective, record, free_only=free_only, excluded={execution.worker_id, *collaborator_ids}, file_ids=request.file_ids)
                resource_used += review_attempts; record.actual_resource_cost += review_attempts; record.manager_resource_cost = max(float(record.manager_resource_cost or 0), record.actual_resource_cost)
                record.quality_decision = decision; record.quality_score = score; record.review_recommendation = decision; record.review_worker_id = reviewer_id; record.rework_number = rework_count; record.rework_problem = problem if decision == "REWORK" else None
                if decision == "REWORK":
                    if rework_count >= 3: record.status = "completed"; records.append(record); return _mission_response("rework_limit_reached", plan, execution_order, "REJECT", rework_count, records, artifact_records, resource_used, request.resource_budget)
                    rework_count += 1; sprint += 1
                    rework_task = _make_rework_task(task, task.task_id, rework_count, sprint); task_by_id[rework_task.task_id] = rework_task
                    review_id = f"quality_review_rework_{rework_count}"; review_task = task_by_id.get("quality_review")
                    if review_task:
                        review_task = review_task.model_copy(update={"task_id": review_id, "title": f"Independent QA for rework #{rework_count}", "dependencies": [rework_task.task_id], "inputs": list(task.outputs), "outputs": [f"quality_review_{rework_count}"], "sprint": sprint}); task_by_id[review_id] = review_task
                        execution_order[index:index + 1] = [rework_task.task_id, review_id]
                    record.status = "completed"; records.append(record); index += 1; continue
                record.status = "reviewed"
            records.append(record); index += 1
        except Exception as exc:
            records.append(TaskExecutionRecord(task_id=task.task_id, task_type=task.task_type, title=task.title, status="failed", sprint=sprint, error=str(exc)[:1000]))
            return _mission_response("failed", plan, execution_order, "REJECT", rework_count, records, artifact_records, resource_used, request.resource_budget)

    final_reviews = [r for r in records if r.task_type == "quality_review" and r.status == "reviewed"]
    if final_reviews and final_reviews[-1].quality_decision != "PASS": return _mission_response("failed", plan, execution_order, "REJECT", rework_count, records, artifact_records, resource_used, request.resource_budget)
    if any(r.status in {"failed", "blocked"} for r in records): return _mission_response("failed", plan, execution_order, "REJECT", rework_count, records, artifact_records, resource_used, request.resource_budget)
    return _mission_response("completed", plan, execution_order, "ACCEPT", rework_count, records, artifact_records, resource_used, request.resource_budget)
