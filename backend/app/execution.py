from __future__ import annotations

from pydantic import BaseModel, Field

from .gemini_connector import generate_text
from .worker_router import route_task


class ExecutionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    task_type: str = Field(default="general_reasoning", min_length=1, max_length=64)


class ExecutionResponse(BaseModel):
    status: str
    task_type: str
    worker_id: str
    worker_name: str
    routing_policy: str
    route_score: float
    output: str
    telemetry: dict[str, object]


def execute_task(request: ExecutionRequest, *, free_only: bool = True) -> ExecutionResponse:
    route = route_task(request.task_type, free_only=free_only)

    if not route.execution_ready or route.recommended_worker_id is None:
        raise RuntimeError(
            f"No execution-ready free worker is available for task type '{request.task_type}'."
        )

    # Stage 6 deliberately executes only through a connector-backed worker.
    # Local tools/validators are routing candidates but do not yet have a
    # generic natural-language executor in this stage.
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
