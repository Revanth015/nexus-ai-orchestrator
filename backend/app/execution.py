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
    error: str | None = None


class MissionExecutionResponse(BaseModel):
    status: str
    objective: str
    execution_order: list[str]
    tasks: list[TaskExecutionRecord]
    artifacts: dict[str, str]


def execute_task(request: ExecutionRequest, *, free_only: bool = True) -> ExecutionResponse:
    route = route_task(request.task_type, free_only=free_only)

    if not route.execution_ready or route.recommended_worker_id is None:
        raise RuntimeError(
            f"No execution-ready free worker is available for task type '{request.task_type}'."
        )

    # Stage 6 executes connector-backed work through Gemini. Local tools and
    # validators remain routing candidates until they have task-specific
    # executors rather than being presented as generic AI workers.
    if route.recommended_worker_id != "gemini":
        raise RuntimeError(
            f"Worker '{route.recommended_worker_id}' is route-ready but has no generic executor in Stage 6."
        )

    result = generate_text(request.prompt)
    candidate = next(
        item for item in route.candidates if item.worker_id == route.recommended_worker_id
    )

    return ExecutionResponse(
        status="completed",
        task_type=request.task_type,
        worker_id=route.recommended_worker_id,
        worker_name=candidate.name,
        routing_policy=route.routing_policy,
        route_score=candidate.score,
        output=result["text"],
        telemetry=result["telemetry"],
    )


def _task_prompt(objective: str, title: str, task_type: str, inputs: list[str], artifacts: dict[str, str]) -> str:
    context = ""
    if inputs:
        supplied = [f"{name}: {artifacts[name]}" for name in inputs if name in artifacts]
        if supplied:
            context = "\n\nPrevious task outputs:\n" + "\n\n".join(supplied)

    return (
        f"Mission objective:\n{objective}\n\n"
        f"Current task: {title}\n"
        f"Task type: {task_type}\n"
        "Complete only this task and produce a concise artifact that downstream tasks can use."
        f"{context}"
    )


def execute_mission(request: MissionExecutionRequest, *, free_only: bool = True) -> MissionExecutionResponse:
    analysis = analyze_prompt(request.prompt)
    plan = build_task_plan(analysis)
    artifacts: dict[str, str] = {}
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
                        artifacts,
                    ),
                ),
                free_only=free_only,
            )
            records.append(TaskExecutionRecord(
                task_id=task.task_id,
                task_type=task.task_type,
                title=task.title,
                status="completed",
                worker_id=execution.worker_id,
                worker_name=execution.worker_name,
                output=execution.output,
                route_score=execution.route_score,
                telemetry=execution.telemetry,
            ))
            for output_name in task.outputs:
                artifacts[output_name] = execution.output
        except Exception as exc:
            records.append(TaskExecutionRecord(
                task_id=task.task_id,
                task_type=task.task_type,
                title=task.title,
                status="failed",
                error=str(exc),
            ))
            break

    status = "completed" if len(records) == len(plan.tasks) and all(
        record.status == "completed" for record in records
    ) else "failed"

    return MissionExecutionResponse(
        status=status,
        objective=plan.objective,
        execution_order=plan.execution_order,
        tasks=records,
        artifacts=artifacts,
    )
