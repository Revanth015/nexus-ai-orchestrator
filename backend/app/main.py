from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .prompt_analyzer import analyze_prompt
from .prompt_models import PromptAnalysisResponse, PromptRequest
from .planner_models import PlanResponse
from .task_planner import build_task_plan

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
