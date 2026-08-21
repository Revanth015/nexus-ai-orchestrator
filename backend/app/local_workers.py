from __future__ import annotations

import re
import time
from datetime import datetime, timezone


def _telemetry(worker_id: str, worker_name: str, latency_ms: float, *, requests: int = 1) -> dict[str, object]:
    return {
        "provider": "local",
        "worker_id": worker_id,
        "model": "deterministic-local-v1",
        "configured": True,
        "execution_ready": True,
        "free_only": True,
        "free_model_verified": True,
        "quota_status": "not_applicable",
        "quota_exact": None,
        "quota_estimate": None,
        "observed_requests": requests,
        "successful_requests": requests,
        "failed_requests": 0,
        "last_success_at": datetime.now(timezone.utc).isoformat(),
        "last_failure_at": None,
        "last_latency_ms": round(latency_ms, 2),
        "failure_class": None,
        "last_error": None,
        "note": "Local deterministic execution; no external AI quota is consumed.",
    }


def execute_local_task(task_type: str, prompt: str) -> dict[str, object]:
    """Execute tasks that can be handled deterministically without an external model."""
    started = time.perf_counter()

    if task_type == "quality_review":
        # The execution prompt contains the upstream artifacts. Apply simple,
        # deterministic gates rather than pretending to perform semantic review.
        text = prompt.strip()
        checks: list[str] = []
        if len(text) >= 120:
            checks.append("sufficient_content")
        else:
            checks.append("content_too_short")
        if "Mission objective:" in text and "Current task:" in text:
            checks.append("task_context_present")
        else:
            checks.append("task_context_missing")
        if "Previous task outputs:" in text:
            checks.append("upstream_artifact_present")
        else:
            checks.append("upstream_artifact_missing")

        passed = all(item.endswith("present") or item == "sufficient_content" for item in checks)
        decision = "PASS" if passed else "REWORK"
        output = (
            "Deterministic quality gate completed.\n"
            f"Checks: {', '.join(checks)}.\n"
            f"{decision}"
        )
        worker_id = "local-validator"
        worker_name = "NEXUS Local Validator"

    elif task_type == "data_analysis":
        text = prompt.strip()
        numbers = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", text)
        words = re.findall(r"\b\w+\b", text)
        unique_words = len({word.lower() for word in words})
        output = (
            "Deterministic local analysis completed.\n"
            f"Input characters: {len(text)}\n"
            f"Word count: {len(words)}\n"
            f"Unique words: {unique_words}\n"
            f"Numeric values detected: {len(numbers)}\n"
            "Note: this local worker performs structural/text analysis only; it does not invent business conclusions."
        )
        worker_id = "local-tools"
        worker_name = "NEXUS Local Tools"

    elif task_type == "file_analysis":
        text = prompt.strip()
        output = (
            "Local file-analysis worker is ready, but no file bytes were supplied to this execution request.\n"
            f"Execution context characters: {len(text)}\n"
            "No file contents were inspected and no file-specific conclusions were generated."
        )
        worker_id = "local-tools"
        worker_name = "NEXUS Local Tools"

    else:
        raise RuntimeError(f"Local worker does not support task type '{task_type}'.")

    latency_ms = (time.perf_counter() - started) * 1000
    return {
        "text": output,
        "worker_id": worker_id,
        "worker_name": worker_name,
        "telemetry": _telemetry(worker_id, worker_name, latency_ms),
    }
