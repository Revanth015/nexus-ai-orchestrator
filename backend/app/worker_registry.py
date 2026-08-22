from __future__ import annotations

from .ai_connectors import claude_status, perplexity_status
from .gemini_connector import runtime_metadata as gemini_runtime_metadata
from .models import CapabilityScores, CorporateRole, FreeStatus, ResourceState, WorkerProfile, WorkerType


_INITIAL_WORKERS = [
    WorkerProfile(worker_id="local-tools", name="NEXUS Local Tools", provider="local", worker_type=WorkerType.LOCAL,
        corporate_role=CorporateRole.EMPLOYEE,
        capabilities=CapabilityScores(reasoning=70, coding=85, documents=80, data_analysis=95, instruction_following=90, reliability=98, efficiency=98),
        resource=ResourceState(free_status=FreeStatus.VERIFIED_FREE, quota_known=True, confidence=100),
        metadata={"connected": True, "execution_ready": True, "notes": "Employee worker for deterministic local execution; no external AI quota."}),
    WorkerProfile(worker_id="perplexity", name="Perplexity", provider="perplexity", worker_type=WorkerType.RESEARCH,
        corporate_role=CorporateRole.EMPLOYEE,
        capabilities=CapabilityScores(reasoning=84, research=95, documents=78, instruction_following=88, reliability=86, efficiency=82),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "Research employee; readiness is measured through its connector."}),
    WorkerProfile(worker_id="gemini", name="Gemini", provider="google", worker_type=WorkerType.AI,
        corporate_role=CorporateRole.EMPLOYEE,
        capabilities=CapabilityScores(reasoning=90, research=82, coding=88, documents=90, presentation=94, data_analysis=88, vision=90, instruction_following=90, reliability=86, efficiency=90),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "General AI employee; readiness is measured through its connector."}),
    WorkerProfile(worker_id="claude", name="Claude", provider="anthropic", worker_type=WorkerType.AI,
        corporate_role=CorporateRole.EMPLOYEE,
        capabilities=CapabilityScores(reasoning=94, research=84, coding=95, documents=94, presentation=86, data_analysis=90, instruction_following=95, reliability=90, efficiency=82),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "Reasoning/coding/document employee; readiness is measured through its connector."}),
    WorkerProfile(worker_id="local-validator", name="NEXUS Quality Review Employee", provider="local", worker_type=WorkerType.VALIDATOR,
        corporate_role=CorporateRole.QA_EMPLOYEE,
        capabilities=CapabilityScores(reasoning=78, documents=88, data_analysis=88, instruction_following=92, reliability=98, efficiency=96),
        resource=ResourceState(free_status=FreeStatus.VERIFIED_FREE, quota_known=True, confidence=100),
        metadata={"connected": True, "execution_ready": True, "notes": "Independent QA employee. Recommends PASS/REWORK; never owns the Manager's final acceptance decision."}),
]


def _apply_ai_telemetry(worker: WorkerProfile) -> WorkerProfile:
    telemetry = gemini_runtime_metadata() if worker.worker_id == "gemini" else claude_status() if worker.worker_id == "claude" else perplexity_status()
    worker.metadata.update({"connected": telemetry["configured"], "execution_ready": telemetry["execution_ready"], "connector_configured": telemetry["configured"]})
    worker.resource.quota_known = bool(telemetry["quota_status"] != "unknown")
    worker.resource.estimated_remaining = telemetry.get("quota_estimate")
    worker.resource.last_error = telemetry.get("last_error")
    worker.resource.observed_requests = telemetry.get("observed_requests", 0)
    worker.resource.free_status = FreeStatus.MEASURED_FREE if telemetry["execution_ready"] else FreeStatus.UNKNOWN
    worker.resource.confidence = 100 if telemetry["execution_ready"] else 0
    return worker


def list_workers() -> list[WorkerProfile]:
    workers = [worker.model_copy(deep=True) for worker in _INITIAL_WORKERS]
    for worker in workers:
        if worker.worker_id in {"gemini", "claude", "perplexity"}:
            _apply_ai_telemetry(worker)
    return workers


def get_worker(worker_id: str) -> WorkerProfile | None:
    return next((worker for worker in list_workers() if worker.worker_id == worker_id), None)
