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
        return {"workers": {}, "version": 3, "collaboration": {}}


def _save(data: dict[str, Any]) -> None:
    _STORE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_result(worker_id: str, *, task_type: str, success: bool, latency_ms: float | None = None, quality: str | None = None, quality_score: float | None = None) -> None:
    """Persist task-specific evidence. Initial capability scores are never overwritten."""
    with _LOCK:
        data = _load()
        worker = data.setdefault("workers", {}).setdefault(worker_id, {"observations": 0, "successes": 0, "failures": 0, "latencies_ms": [], "quality_passes": 0, "quality_reworks": 0, "tasks": {}, "collaboration": {}})
        worker["observations"] += 1
        worker["successes"] += int(success)
        worker["failures"] += int(not success)
        if latency_ms is not None:
            worker["latencies_ms"] = (worker.get("latencies_ms", []) + [round(float(latency_ms), 2)])[-50:]
        if quality == "PASS":
            worker["quality_passes"] += 1
        elif quality == "REWORK":
            worker["quality_reworks"] += 1
        task = worker.setdefault("tasks", {}).setdefault(task_type, {"observations": 0, "successes": 0, "failures": 0, "latencies_ms": [], "quality_passes": 0, "quality_reworks": 0})
        task["observations"] += 1
        task["successes"] += int(success)
        task["failures"] += int(not success)
        if latency_ms is not None:
            task["latencies_ms"] = (task.get("latencies_ms", []) + [round(float(latency_ms), 2)])[-50:]
        if quality == "PASS":
            task["quality_passes"] += 1
        elif quality == "REWORK":
            task["quality_reworks"] += 1
        if quality_score is not None:
            scores = (task.get("quality_scores", []) + [float(quality_score)])[-50:]
            task["quality_scores"] = scores
        worker["last_observed_at"] = datetime.now(timezone.utc).isoformat()
        _save(data)


def record_collaboration(source_worker_id: str, support_worker_id: str, *, task_type: str, success: bool, latency_ms: float | None = None) -> None:
    """Record whether a worker pair successfully collaborated on a specific task."""
    with _LOCK:
        data = _load()
        key = f"{source_worker_id}::{support_worker_id}"
        pair = data.setdefault("collaboration", {}).setdefault(key, {"source_worker_id": source_worker_id, "support_worker_id": support_worker_id, "observations": 0, "successes": 0, "failures": 0, "tasks": {}})
        pair["observations"] += 1
        pair["successes"] += int(success)
        pair["failures"] += int(not success)
        task = pair.setdefault("tasks", {}).setdefault(task_type, {"observations": 0, "successes": 0, "failures": 0})
        task["observations"] += 1
        task["successes"] += int(success)
        task["failures"] += int(not success)
        if latency_ms is not None:
            pair["last_latency_ms"] = round(float(latency_ms), 2)
        _save(data)


def get_worker_learning(worker_id: str) -> dict[str, Any]:
    with _LOCK:
        return _load().get("workers", {}).get(worker_id, {})


def task_performance(worker_id: str, task_type: str) -> dict[str, float]:
    worker = get_worker_learning(worker_id)
    task = worker.get("tasks", {}).get(task_type, {})
    observations = int(task.get("observations", 0))
    if observations <= 0:
        return {"score": 0.0, "confidence": 0.0, "success_rate": 0.0, "rework_rate": 0.0, "avg_latency_ms": 0.0, "observations": 0}
    success_rate = float(task.get("successes", 0)) / observations
    reworks = int(task.get("quality_reworks", 0))
    passes = int(task.get("quality_passes", 0))
    reviewed = reworks + passes
    rework_rate = reworks / reviewed if reviewed else 0.0
    latencies = task.get("latencies_ms", [])
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    quality_scores = task.get("quality_scores", [])
    quality = sum(quality_scores) / len(quality_scores) if quality_scores else success_rate * 100.0
    score = max(0.0, min(100.0, quality * 0.55 + success_rate * 100.0 * 0.25 + (100.0 - rework_rate * 100.0) * 0.15 + max(0.0, min(100.0, 100.0 - avg_latency / 100.0)) * 0.05))
    confidence = min(100.0, observations / 20.0 * 100.0)
    return {"score": round(score, 2), "confidence": round(confidence, 2), "success_rate": round(success_rate * 100, 2), "rework_rate": round(rework_rate * 100, 2), "avg_latency_ms": round(avg_latency, 2), "observations": observations}


def learned_adjustments(worker_id: str, task_type: str) -> dict[str, float]:
    performance = task_performance(worker_id, task_type)
    if performance["observations"] <= 0:
        return {"reliability": 0.0, "efficiency": 0.0}
    return {
        "reliability": (performance["success_rate"] - 50.0) * 0.12,
        "efficiency": max(-5.0, min(5.0, (3000.0 - performance["avg_latency_ms"]) / 600.0)),
    }


def learning_snapshot() -> dict[str, Any]:
    with _LOCK:
        return _load()


def self_initialize() -> dict[str, Any]:
    """Create onboarding records for newly discovered workers without resetting existing evidence."""
    from .worker_registry import list_workers
    now = datetime.now(timezone.utc).isoformat()
    workers = list_workers()
    results = []
    with _LOCK:
        data = _load()
        for worker in workers:
            existing = data.setdefault("workers", {}).setdefault(worker.worker_id, {"observations": 0, "successes": 0, "failures": 0, "latencies_ms": [], "quality_passes": 0, "quality_reworks": 0, "tasks": {}, "collaboration": {}})
            if "onboarding" not in existing:
                existing["onboarding"] = {"status": "pending", "initialized_at": now, "initial_capabilities": worker.capabilities.model_dump(exclude_none=True), "tests": [], "note": "Initial capability profile is a prior; real task evidence updates task-specific performance."}
            results.append({"worker_id": worker.worker_id, "onboarding_status": existing["onboarding"]["status"], "observations": existing.get("observations", 0), "initial_capabilities": existing["onboarding"].get("initial_capabilities", {})})
        _save(data)
    return {"status": "initialized", "timestamp": now, "workers": results, "policy": "new_workers_get_onboarding; existing_workers_keep_history"}
