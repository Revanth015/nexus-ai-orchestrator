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


def _file_summary(file_context: list[dict[str, object]]) -> str:
    if not file_context:
        return "No uploaded files were supplied."
    lines = []
    for item in file_context:
        content = str(item.get("content", ""))
        lines.append(
            f"File: {item.get('filename', item.get('file_id', 'unknown'))}\n"
            f"Type: {item.get('extension', 'unknown')}\n"
            f"Extracted characters: {len(content)}\n"
            f"Preview:\n{content[:4000]}"
        )
    return "\n\n".join(lines)


def execute_local_task(
    task_type: str,
    prompt: str,
    *,
    file_context: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Execute deterministic tasks locally, optionally using extracted uploaded files."""
    started = time.perf_counter()
    files = file_context or []

    if task_type == "quality_review":
        text = prompt.strip()
        checks: list[str] = []
        checks.append("sufficient_content" if len(text) >= 120 else "content_too_short")
        checks.append("task_context_present" if "Mission objective:" in text and "Current task:" in text else "task_context_missing")
        checks.append("upstream_artifact_present" if "Previous task outputs:" in text else "upstream_artifact_missing")
        checks.append("uploaded_file_present" if files else "uploaded_file_not_supplied")
        passed = all(item.endswith("present") or item == "sufficient_content" for item in checks)
        decision = "PASS" if passed else "REWORK"
        output = "Deterministic quality gate completed.\n" f"Checks: {', '.join(checks)}.\n" f"{decision}"
        worker_id = "local-validator"
        worker_name = "NEXUS Local Validator"

    elif task_type == "data_analysis":
        text = prompt.strip()
        file_text = _file_summary(files)
        combined = f"{text}\n\n{file_text}"
        numbers = [float(value) for value in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", combined)]
        words = re.findall(r"\b\w+\b", combined)
        unique_words = len({word.lower() for word in words})
        numeric_summary = "No numeric values detected."
        if numbers:
            average = sum(numbers) / len(numbers)
            numeric_summary = f"Numeric values: {len(numbers)}\nNumeric average: {average:.2f}\nNumeric maximum: {max(numbers):.2f}"
        output = (
            "Deterministic local analysis completed.\n"
            f"Uploaded files: {len(files)}\n"
            f"Input characters: {len(combined)}\n"
            f"Word count: {len(words)}\n"
            f"Unique words: {unique_words}\n"
            f"{numeric_summary}\n"
            "Note: calculations are deterministic; semantic business conclusions are not invented."
        )
        if files:
            output += "\n\nFile summaries:\n" + "\n\n".join(
                f"{item.get('filename', 'file')}: {item.get('extension', '')}, {len(str(item.get('content', '')))} extracted characters"
                for item in files
            )
        worker_id = "local-tools"
        worker_name = "NEXUS Local Tools"

    elif task_type == "file_analysis":
        text = prompt.strip()
        if not files:
            output = (
                "Local file-analysis worker received no uploaded file.\n"
                f"Execution context characters: {len(text)}\n"
                "No file-specific conclusions were generated."
            )
        else:
            output = (
                "Local file analysis completed.\n"
                f"Files inspected: {len(files)}\n"
                + "\n".join(
                    f"- {item.get('filename', 'file')}: {item.get('extension', '')}, {len(str(item.get('content', '')))} extracted characters"
                    for item in files
                )
                + "\n\nExtracted preview:\n"
                + _file_summary(files)
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
