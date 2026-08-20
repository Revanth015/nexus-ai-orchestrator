from __future__ import annotations

from .gemini_connector import runtime_metadata as gemini_runtime_metadata
from .models import CapabilityScores, FreeStatus, ResourceState, WorkerProfile, WorkerType


# Capability values are initial routing priors, not claims about live quotas.
# They are adjusted by connector telemetry when a provider is actually tested.
_INITIAL_WORKERS = [
    WorkerProfile(
        worker_id="local-tools",
        name="NEXUS Local Tools",
        provider="local",
        worker_type=WorkerType.LOCAL,
        capabilities=CapabilityScores(
            reasoning=70, coding=85, documents=80, data_analysis=95,
            instruction_following=90, reliability=98, efficiency=98,
        ),
        resource=ResourceState(
            free_status=FreeStatus.VERIFIED_FREE,
            quota_known=True,
            provider_remaining=None,
            confidence=100,
        ),
        metadata={"connected": True, "execution_ready": True, "notes": "Local execution; no external AI quota."},
    ),
    WorkerProfile(
        worker_id="perplexity",
        name="Perplexity",
        provider="perplexity",
        worker_type=WorkerType.RESEARCH,
        capabilities=CapabilityScores(
            reasoning=84, research=95, documents=78, instruction_following=88,
            reliability=86, efficiency=82,
        ),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "Research-oriented worker; quota must be observed through its connector."},
    ),
    WorkerProfile(
        worker_id="gemini",
        name="Gemini",
        provider="google",
        worker_type=WorkerType.AI,
        capabilities=CapabilityScores(
            reasoning=90, research=82, coding=88, documents=90, presentation=94,
            data_analysis=88, vision=90, instruction_following=90, reliability=86, efficiency=90,
        ),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "General multimodal worker; free availability is measured through its connector."},
    ),
    WorkerProfile(
        worker_id="claude",
        name="Claude",
        provider="anthropic",
        worker_type=WorkerType.AI,
        capabilities=CapabilityScores(
            reasoning=94, research=84, coding=95, documents=94, presentation=86,
            data_analysis=90, instruction_following=95, reliability=90, efficiency=82,
        ),
        resource=ResourceState(free_status=FreeStatus.UNKNOWN, confidence=0),
        metadata={"connected": False, "execution_ready": False, "notes": "Reasoning/coding/document worker; free availability must be measured."},
    ),
    WorkerProfile(
        worker_id="local-validator",
        name="NEXUS Local Validator",
        provider="local",
        worker_type=WorkerType.VALIDATOR,
        capabilities=CapabilityScores(
            reasoning=78, documents=88, data_analysis=88, instruction_following=92,
            reliability=98, efficiency=96,
        ),
        resource=ResourceState(free_status=FreeStatus.VERIFIED_FREE, quota_known=True, confidence=100),
        metadata={"connected": True, "execution_ready": True, "notes": "Deterministic validation layer; later can be supplemented by AI reviewers."},
    ),
]


def _apply_gemini_telemetry(worker: WorkerProfile) -> WorkerProfile:
    telemetry = gemini_runtime_metadata()
    worker.metadata.update({
        "connected": telemetry["connected"],
        "execution_ready": telemetry["execution_ready"],
        "connector_configured": telemetry["configured"],
    })
    worker.resource.quota_known = bool(telemetry["quota_known"])
    worker.resource.estimated_remaining = telemetry["estimated_remaining"]
    worker.resource.last_error = telemetry["last_error"]
    worker.resource.observed_requests = telemetry["observed_requests"]
    if telemetry["execution_ready"]:
        worker.resource.free_status = FreeStatus.MEASURED_FREE
        worker.resource.confidence = 100
    elif telemetry["configured"]:
        worker.resource.free_status = FreeStatus.UNKNOWN
    else:
        worker.resource.free_status = FreeStatus.UNKNOWN
    return worker


def list_workers() -> list[WorkerProfile]:
    """Return request-time worker profiles with safe live connector telemetry."""
    workers = [worker.model_copy(deep=True) for worker in _INITIAL_WORKERS]
    for worker in workers:
        if worker.worker_id == "gemini":
            _apply_gemini_telemetry(worker)
    return workers


def get_worker(worker_id: str) -> WorkerProfile | None:
    return next((worker for worker in list_workers() if worker.worker_id == worker_id), None)
