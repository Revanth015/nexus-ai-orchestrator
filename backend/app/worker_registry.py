from __future__ import annotations

from .models import CapabilityScores, FreeStatus, ResourceState, WorkerProfile, WorkerType


# Capability values are initial routing priors, not claims about live quotas.
# They will be replaced/adjusted by measured job telemetry once connectors exist.
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
        metadata={"connected": False, "execution_ready": False, "notes": "General multimodal worker; free availability must be measured, not assumed."},
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


def list_workers() -> list[WorkerProfile]:
    """Return fresh copies so request-time telemetry cannot mutate registry constants."""
    return [worker.model_copy(deep=True) for worker in _INITIAL_WORKERS]


def get_worker(worker_id: str) -> WorkerProfile | None:
    return next((worker for worker in list_workers() if worker.worker_id == worker_id), None)
