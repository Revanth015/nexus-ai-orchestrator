from __future__ import annotations

from .ai_connectors import claude_status, perplexity_status
from .gemini_connector import runtime_metadata as gemini_runtime_metadata
from .models import CapabilityScores, FreeStatus, ResourceState, WorkerProfile, WorkerType
from .worker_learning import get_worker_learning, record_result, task_performance


_INITIAL_WORKERS = [
    WorkerProfile(worker_id="local-tools", name="NEXUS Local Tools", provider="local", worker_type=WorkerType.LOCAL,
        capabilities=CapabilityScores(reasoning=70, coding=85, documents=80, data_analysis=95, instruction_following=90, reliability=98, efficiency=98),
        resource=ResourceState(free_status=FreeStatus.VERIFIED_FREE, quota_known=True, confidence=100),
        metadata={"connected": True, "execution_ready": True, "notes": "Deterministic local worker; no external AI quota."}),
    WorkerProfile(worker_id="perplexity", name="Perplexity", provider="perplexity", worker_type=WorkerType.RESEARCH,
        capabilities=CapabilityScores(reasoning=84, research=95, documents=78, instruction_following=88, reliability=86, efficiency=82),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "Research-capable worker; routing is task-specific."}),
    WorkerProfile(worker_id="gemini", name="Gemini", provider="google", worker_type=WorkerType.AI,
        capabilities=CapabilityScores(reasoning=90, research=82, coding=88, documents=90, presentation=94, data_analysis=88, vision=90, instruction_following=90, reliability=86, efficiency=90),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "General AI worker; routing is task-specific."}),
    WorkerProfile(worker_id="claude", name="Claude", provider="anthropic", worker_type=WorkerType.AI,
        capabilities=CapabilityScores(reasoning=94, research=84, coding=95, documents=94, presentation=86, data_analysis=90, instruction_following=95, reliability=90, efficiency=82),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "General AI worker; routing is task-specific."}),
    WorkerProfile(worker_id="local-validator", name="NEXUS Local Validator", provider="local", worker_type=WorkerType.VALIDATOR,
        capabilities=CapabilityScores(reasoning=78, documents=88, data_analysis=88, instruction_following=92, reliability=98, efficiency=96),
        resource=ResourceState(free_status=FreeStatus.VERIFIED_FREE, quota_known=True, confidence=100),
        metadata={"connected": True, "execution_ready": True, "notes": "Deterministic validation worker; can be selected dynamically for review tasks."}),
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
        learning = get_worker_learning(worker.worker_id)
        if learning:
            worker.metadata["observed_performance"] = {
                "observations": learning.get("observations", 0),
                "successes": learning.get("successes", 0),
                "failures": learning.get("failures", 0),
                "quality_passes": learning.get("quality_passes", 0),
                "quality_reworks": learning.get("quality_reworks", 0),
                "last_observed_at": learning.get("last_observed_at"),
                "task_profiles": learning.get("tasks", {}),
                "collaboration": learning.get("collaboration", {}),
            }
    return workers


def get_worker(worker_id: str) -> WorkerProfile | None:
    return next((worker for worker in list_workers() if worker.worker_id == worker_id), None)
