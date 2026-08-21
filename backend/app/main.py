from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .execution import (
    ExecutionRequest,
    ExecutionResponse,
    MissionExecutionRequest,
    MissionExecutionResponse,
    execute_mission,
    execute_task,
)
from .gemini_connector import GeminiStatus, GeminiTestRequest, status as gemini_status, test_connection
from .prompt_analyzer import analyze_prompt
from .prompt_models import PromptAnalysisResponse, PromptRequest
from .planner_models import PlanResponse
from .task_planner import build_task_plan
from .worker_registry import list_workers
from .worker_router import WorkerRouteResponse, route_task

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Free-first AI orchestration backend for NEXUS.",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "free_only": settings.free_only,
        "background_execution": settings.background_execution,
    }


@app.post("/analyze", response_model=PromptAnalysisResponse)
def analyze(request: PromptRequest) -> PromptAnalysisResponse:
    return PromptAnalysisResponse(
        prompt=request.prompt,
        analysis=analyze_prompt(request.prompt),
    )


@app.post("/plan", response_model=PlanResponse)
def plan(request: PromptRequest) -> PlanResponse:
    analysis = analyze_prompt(request.prompt)
    return PlanResponse(plan=build_task_plan(analysis))


@app.get("/workers")
def workers() -> dict[str, object]:
    """Return the current worker registry with live connector telemetry."""
    return {
        "free_only": settings.free_only,
        "workers": [worker.model_dump(mode="json") for worker in list_workers()],
        "note": "Capability scores are initial routing priors; connector telemetry updates readiness and observed resource state.",
    }


@app.get("/route/{task_type}", response_model=WorkerRouteResponse)
def route(task_type: str) -> WorkerRouteResponse:
    """Recommend workers using capability priors and free-first execution readiness."""
    return route_task(task_type, free_only=settings.free_only)


@app.post("/execute", response_model=ExecutionResponse)
def execute(request: ExecutionRequest) -> ExecutionResponse:
    """Route one explicit task to an execution-ready free worker and run it."""
    try:
        return execute_task(request, free_only=settings.free_only)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/execute-mission", response_model=MissionExecutionResponse)
def execute_mission_endpoint(request: MissionExecutionRequest) -> MissionExecutionResponse:
    """Execute every planned task in dependency order, carrying artifacts downstream."""
    try:
        return execute_mission(request, free_only=settings.free_only)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/connectors/gemini/status", response_model=GeminiStatus)
def gemini_connector_status() -> GeminiStatus:
    """Return Gemini configuration and observed telemetry without making a model call."""
    return gemini_status()


@app.post("/connectors/gemini/test")
def gemini_connector_test(request: GeminiTestRequest) -> dict[str, object]:
    """Make one explicit Gemini test call. This endpoint never runs automatically."""
    try:
        return {
            "status": "ok",
            "result": test_connection(request.prompt),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
