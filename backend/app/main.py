from fastapi import FastAPI

from .config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Free-first AI orchestration backend for NEXUS.",
)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "free_only": settings.free_only,
        "background_execution": settings.background_execution,
    }
