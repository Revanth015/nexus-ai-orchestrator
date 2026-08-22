from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


_STORE = Path(__file__).resolve().parent.parent / ".nexus_worker_learning.json"
_LOCK = Lock()


def _load() -> dict[str, Any]:
    try:
        return json.loads(_STORE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"workers": {}, "version": 1}


def _save(data: dict[str, Any]) -> None:
    _STORE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_result(worker_id: str, *, task_type: str, success: bool, latency_ms: float | None = None, quality: str | None = None) -> None:
    """Persist observed worker performance. These are routing adjustments, not ground-truth claims."""
    with _LOCK:
        data = _load()
        worker = data.setdefault("workers", {}).setdefault(worker_id, {"observations": 0, "successes": 0, "failures": 0, "latencies_ms": [], "quality_passes": 0, "quality_reworks": 0, "tasks": {}})
        worker["observations"] += 1
        worker["successes"] += int(success)
        worker["failures"] += int(not success)
        if latency_ms is not None:
            worker["latencies_ms"] = (worker.get("latencies_ms", []) + [round(float(latency_ms), 2)])[-20:]
        if quality == "PASS":
            worker["quality_passes"] += 1
        elif quality == "REWORK":
            worker["quality_reworks"] += 1
        task = worker.setdefault("tasks", {}).setdefault(task_type, {"observations": 0, "successes": 0, "failures": 0})
        task["observations"] += 1
        task["successes"] += int(success)
        task["failures"] += int(not success)
        worker["last_observed_at"] = datetime.now(timezone.utc).isoformat()
        _save(data)


def get_worker_learning(worker_id: str) -> dict[str, Any]:
    with _LOCK:
        return _load().get("workers", {}).get(worker_id, {})


def learned_adjustments(worker_id: str, task_type: str) -> dict[str, float]:
    worker = get_worker_learning(worker_id)
    task = worker.get("tasks", {}).get(task_type, {})
    observations = int(task.get("observations", 0))
    if observations <= 0:
        return {"reliability": 0.0, "efficiency": 0.0}
    success_rate = float(task.get("successes", 0)) / observations
    reliability = (success_rate - 0.5) * 12.0
    latencies = worker.get("latencies_ms", [])
    efficiency = 0.0
    if latencies:
        avg = sum(latencies) / len(latencies)
        efficiency = max(-5.0, min(5.0, (3000.0 - avg) / 600.0))
    return {"reliability": reliability, "efficiency": efficiency}


def learning_snapshot() -> dict[str, Any]:
    with _LOCK:
        return _load()


def self_initialize() -> dict[str, Any]:
    """Rebuild the runtime routing view from live connector readiness plus observed results."""
    from .worker_registry import list_workers

    workers = list_workers()
    return {
        "status": "initialized",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workers": [
            {
                "worker_id": w.worker_id,
                "corporate_role": w.corporate_role.value,
                "execution_ready": bool(w.metadata.get("execution_ready")),
                "observations": get_worker_learning(w.worker_id).get("observations", 0),
            }
            for w in workers
        ],
    }
