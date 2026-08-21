from __future__ import annotations

from pydantic import BaseModel, Field

from .gemini_connector import generate_text
from .prompt_analyzer import analyze_prompt
from .task_planner import build_task_plan
from .worker_router import route_task


class ExecutionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    task_type: str = Field(default="general_reasoning", min_length=1, max_length=64)


class MissionExecutionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)


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
    artifact_ids: list[str] = []
    quality_decision: str | None = None
    error: str | None = None


class MissionExecutionResponse(BaseModel):
    status: str
    objective: str
    execution_order: list[str]
    tasks: list[TaskExecutionRecord]
    artifacts: list[ArtifactRecord]


def execute_task(request: ExecutionRequest, *, free_only: bool = True) -> ExecutionResponse:
    route = route_task(request.task_type, free_only=free_only)

    if not route.execution_ready:
        raise RuntimeError(
            f"No execution-ready free worker is available for task type '{request.task_type}'."
        )

    executable_candidate = next(
        (
            item for item in route.candidates
            if item.worker_id == "gemini" and item.execution_ready
        ),
        None,
    )
    if executable_candidate is None:
        raise RuntimeError(
            f"Worker routing is ready for '{request.task_type}', but no generic connector executor is currently available."
        )

    result = generate_text(request.prompt)

    return ExecutionResponse(
        status="completed",
        task_type=request.task_type,
        worker_id=executable_candidate.worker_id,
        worker_name=executable_candidate.name,
        routing_policy=route.routing_policy,
        route_score=executable_candidate.score,
        output=result["text"],
        telemetry=result["telemetry"],
    )


def _task_prompt(objective: str, title: str, task_type: str, inputs: list[str], artifacts: dict[str, str]) -> str:
    context = ""
    if inputs:
        supplied = [f"{name}: {artifacts[name]}" for name in inputs if name in artifacts]
        if supplied:
            context = "\n\nPrevious task outputs:\n" + "\n\n".join(supplied)

    quality_instruction = ""
    if task_type == "quality_review":
        quality_instruction = (
            "\n\nQUALITY GATE: Review the supplied upstream artifacts for important factual, "
            "structural, completeness, and consistency problems. End your response with "
            "a separate final line containing exactly PASS or REWORK."
        )

    return (
        f"Mission objective:\n{objective}\n\n"
        f"Current task: {title}\n"
        f"Task type: {task_type}\n"
        "Complete only this task and produce a concise artifact that downstream tasks can use."
        f"{quality_instruction}{context}"
    )


def _artifact_type(task_type: str) -> str:
    return {
        "research": "research_brief",
        "file_analysis": "file_analysis",
        "data_analysis": "analysis_findings",
        "presentation": "presentation_draft",
        "quality_review": "quality_review",
        "writing": "written_draft",
        "image_generation": "image_output",
        "coding": "code_output",
        "general_reasoning": "reasoning_output",
    }.get(task_type, "task_output")


def _quality_decision(output: str) -> str | None:
    for line in reversed([line.strip().upper() for line in output.splitlines() if line.strip()]):
        if line in {"PASS", "REWORK"}:
            return line
    return None


def execute_mission(request: MissionExecutionRequest, *, free_only: bool = True) -> MissionExecutionResponse:
    analysis = analyze_prompt(request.prompt)
    plan = build_task_plan(analysis)
    artifacts_by_name: dict[str, str] = {}
    artifact_records: list[ArtifactRecord] = []
    records: list[TaskExecutionRecord] = []

    task_by_id = {task.task_id: task for task in plan.tasks}

    for task_id in plan.execution_order:
        task = task_by_id[task_id]
        missing = [
            dependency
            for dependency in task.dependencies
            if not any(record.task_id == dependency and record.status == "completed" for record in records)
        ]
        if missing:
            records.append(TaskExecutionRecord(
                task_id=task.task_id,
                task_type=task.task_type,
                title=task.title,
                status="blocked",
                error=f"Dependencies not completed: {', '.join(missing)}",
            ))
            break

        try:
            execution = execute_task(
                ExecutionRequest(
                    task_type=task.task_type,
                    prompt=_task_prompt(
                        plan.objective,
                        task.title,
                        task.task_type,
                        task.inputs,
                        artifacts_by_name,
                    ),
                ),
                free_only=free_only,
            )

            artifact_ids: list[str] = []
            for output_name in task.outputs:
                artifact_id = f"{task.task_id}:{output_name}"
                content = execution.output
                artifact_records.append(ArtifactRecord(
                    artifact_id=artifact_id,
                    task_id=task.task_id,
                    name=output_name,
                    artifact_type=_artifact_type(task.task_type),
                    content=content,
                    size_chars=len(content),
                    preview=content[:280].replace("\n", " "),
                ))
                artifacts_by_name[output_name] = content
                artifact_ids.append(artifact_id)

            decision = _quality_decision(execution.output) if task.quality_gate else None
            task_status = "completed"
            if task.quality_gate and decision == "REWORK":
                task_status = "rework_required"

            records.append(TaskExecutionRecord(
                task_id=task.task_id,
                task_type=task.task_type,
                title=task.title,
                status=task_status,
                worker_id=execution.worker_id,
                worker_name=execution.worker_name,
                output=execution.output,
                route_score=execution.route_score,
                telemetry=execution.telemetry,
                artifact_ids=artifact_ids,
                quality_decision=decision,
            ))

            if task.quality_gate and decision == "REWORK":
                break
        except Exception as exc:
            records.append(TaskExecutionRecord(
                task_id=task.task_id,
                task_type=task.task_type,
                title=task.title,
                status="failed",
                error=str(exc),
            ))
            break

    if records and records[-1].status == "rework_required":
        status = "rework_required"
    elif len(records) == len(plan.tasks) and all(record.status == "completed" for record in records):
        status = "completed"
    else:
        status = "failed"

    return MissionExecutionResponse(
        status=status,
        objective=plan.objective,
        execution_order=plan.execution_order,
        tasks=records,
        artifacts=artifact_records,
    )
