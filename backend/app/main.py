from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .execution import ExecutionRequest, ExecutionResponse, MissionExecutionRequest, MissionExecutionResponse, execute_mission, execute_task
from .file_store import save_upload
from .gemini_connector import GeminiStatus, GeminiTestRequest, status as gemini_status, test_connection
from .ai_connectors import claude_status, perplexity_status, test_claude, test_perplexity
from .planner_models import PlanResponse
from .prompt_analyzer import analyze_prompt
from .prompt_models import PromptAnalysisResponse, PromptRequest
from .task_planner import build_task_plan
from .worker_learning import learning_snapshot, self_initialize, run_self_initialization
from .worker_registry import list_workers
from .worker_router import WorkerRouteResponse, route_task
from .collaboration_planner import CollaborationDecision, collaboration_history, plan_collaboration

app = FastAPI(title=settings.app_name, version="0.1.0", description="Free-first AI orchestration backend for NEXUS.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "service": settings.app_name, "free_only": settings.free_only, "background_execution": settings.background_execution}

@app.post("/analyze", response_model=PromptAnalysisResponse)
def analyze(request: PromptRequest) -> PromptAnalysisResponse:
    return PromptAnalysisResponse(prompt=request.prompt, analysis=analyze_prompt(request.prompt))

@app.post("/plan", response_model=PlanResponse)
def plan(request: PromptRequest) -> PlanResponse:
    analysis = analyze_prompt(request.prompt)
    return PlanResponse(plan=build_task_plan(analysis))

@app.post("/files/upload")
async def upload_file(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        content = await file.read()
        return {"status": "uploaded", "file": save_upload(file.filename or "uploaded_file", content)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File upload failed: {exc}") from exc

@app.get("/workers")
def workers() -> dict[str, object]:
    return {"free_only": settings.free_only, "workers": [worker.model_dump(mode="json") for worker in list_workers()], "note": "Routing scores are dynamic priors: live connector readiness plus observed employee performance update allocation over time."}

@app.get("/workers/learning")
def workers_learning() -> dict[str, object]:
    return learning_snapshot()

@app.get("/workers/collaboration")
def workers_collaboration() -> dict[str, object]:
    return collaboration_history()

@app.post("/workers/self-initialize")
def workers_self_initialize() -> dict[str, object]:
    return self_initialize()

@app.post("/workers/self-initialize/run")
def workers_self_initialize_run() -> dict[str, object]:
    try:
        return run_self_initialization()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Worker self-initialization failed: {exc}") from exc

@app.get("/route/{task_type}", response_model=WorkerRouteResponse)
def route(task_type: str) -> WorkerRouteResponse:
    return route_task(task_type, free_only=settings.free_only)

@app.post("/collaboration/plan", response_model=CollaborationDecision)
def collaboration_plan(request: PromptRequest) -> CollaborationDecision:
    analysis = analyze_prompt(request.prompt)
    task_type = analysis.task_types[0] if analysis.task_types else "general_reasoning"
    return plan_collaboration(task_type, request.prompt, free_only=settings.free_only)

@app.post("/execute", response_model=ExecutionResponse)
def execute(request: ExecutionRequest) -> ExecutionResponse:
    try:
        return execute_task(request, free_only=settings.free_only)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.post("/execute-mission", response_model=MissionExecutionResponse)
def execute_mission_endpoint(request: MissionExecutionRequest) -> MissionExecutionResponse:
    try:
        return execute_mission(request, free_only=settings.free_only)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/connectors/gemini/status", response_model=GeminiStatus)
def gemini_connector_status() -> GeminiStatus:
    return gemini_status()

@app.post("/connectors/gemini/test")
def gemini_connector_test(request: GeminiTestRequest) -> dict[str, object]:
    try:
        return {"status": "ok", "result": test_connection(request.prompt)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/connectors/claude/status")
def claude_connector_status() -> dict[str, object]:
    return claude_status()

@app.post("/connectors/claude/test")
def claude_connector_test(request: GeminiTestRequest) -> dict[str, object]:
    try:
        return {"status": "ok", "result": test_claude(request.prompt)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/connectors/perplexity/status")
def perplexity_connector_status() -> dict[str, object]:
    return perplexity_status()

@app.post("/connectors/perplexity/test")
def perplexity_connector_test(request: GeminiTestRequest) -> dict[str, object]:
    try:
        return {"status": "ok", "result": test_perplexity(request.prompt)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
