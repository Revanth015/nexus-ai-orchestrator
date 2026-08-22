from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

_STORE = Path(__file__).resolve().parent.parent / ".nexus_worker_learning.json"
_LOCK = Lock()

_CAPABILITY_TESTS = {
    "reasoning": [
        {"id": "reasoning_logic_01", "metric": "reasoning_accuracy", "prompt": "Solve this logic task and give only the final answer plus a one-sentence justification: If all A are B and no B are C, can any A be C?"},
        {"id": "reasoning_constraints_01", "metric": "instruction_adherence", "prompt": "Return exactly three numbered items, each containing exactly five words, describing good decision-making."},
    ],
    "research": [
        {"id": "research_synthesis_01", "metric": "research_synthesis", "prompt": "Explain how you would research a market-entry decision. Specify evidence types, source-quality checks, conflicting-evidence handling, and a concise synthesis method. Do not invent sources."},
        {"id": "research_claims_01", "metric": "evidence_discipline", "prompt": "Give three example business claims and label exactly what evidence would be required to verify each claim. Do not claim the examples are factual."},
    ],
    "data_analysis": [
        {"id": "data_calculation_01", "metric": "calculation_accuracy", "prompt": "For sales values 100, 120, 150, 130, 180 calculate the mean, median, maximum and range. Show the calculations."},
        {"id": "data_interpretation_01", "metric": "data_interpretation", "prompt": "Using sales values 100, 120, 150, 130, 180, identify one defensible pattern and one conclusion that cannot be established from this data alone."},
    ],
    "documents": [
        {"id": "documents_completeness_01", "metric": "document_completeness", "prompt": "Draft a concise executive update with objective, current status, three findings, two risks and three next actions. Clearly label every section."},
        {"id": "documents_adherence_01", "metric": "instruction_adherence", "prompt": "Write exactly 80 words explaining why version control matters in a corporate AI workflow."},
    ],
    "coding": [
        {"id": "coding_logic_01", "metric": "coding_correctness", "prompt": "Write a Python function named average(values) that returns the arithmetic mean and raises ValueError for an empty list. Include a short test."},
        {"id": "coding_debug_01", "metric": "debugging", "prompt": "Identify the bug in: result = total / count; count = 0. Explain the failure and give the corrected approach."},
    ],
    "presentation": [
        {"id": "presentation_structure_01", "metric": "presentation_structure", "prompt": "Design a six-slide executive presentation structure for a business expansion recommendation. State the purpose of every slide."},
    ],
    "vision": [
        {"id": "vision_readiness_01", "metric": "vision_readiness", "prompt": "You may not have an image in this test. Explain how you would inspect a supplied business image, identify visual evidence, distinguish observation from inference, and report uncertainty."},
    ],
}


def _default_worker() -> dict[str, Any]:
    return {"observations": 0, "successes": 0, "failures": 0, "latencies_ms": [], "quality_passes": 0, "quality_reworks": 0, "tasks": {}, "collaboration": {}}


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_STORE.read_text(encoding="utf-8"))
        data.setdefault("workers", {})
        data.setdefault("collaboration", {})
        data["version"] = max(int(data.get("version", 1)), 4)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"workers": {}, "version": 4, "collaboration": {}}


def _save(data: dict[str, Any]) -> None:
    _STORE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_result(worker_id: str, *, task_type: str, success: bool, latency_ms: float | None = None, quality: str | None = None, quality_score: float | None = None) -> None:
    with _LOCK:
        data = _load()
        worker = data.setdefault("workers", {}).setdefault(worker_id, _default_worker())
        worker["observations"] += 1
        worker["successes"] += int(success)
        worker["failures"] += int(not success)
        if latency_ms is not None:
            worker["latencies_ms"] = (worker.get("latencies_ms", []) + [round(float(latency_ms), 2)])[-50:]
        if quality == "PASS": worker["quality_passes"] += 1
        elif quality == "REWORK": worker["quality_reworks"] += 1
        task = worker.setdefault("tasks", {}).setdefault(task_type, {"observations": 0, "successes": 0, "failures": 0, "latencies_ms": [], "quality_passes": 0, "quality_reworks": 0})
        task["observations"] += 1
        task["successes"] += int(success)
        task["failures"] += int(not success)
        if latency_ms is not None: task["latencies_ms"] = (task.get("latencies_ms", []) + [round(float(latency_ms), 2)])[-50:]
        if quality == "PASS": task["quality_passes"] += 1
        elif quality == "REWORK": task["quality_reworks"] += 1
        if quality_score is not None: task["quality_scores"] = (task.get("quality_scores", []) + [float(quality_score)])[-50:]
        worker["last_observed_at"] = datetime.now(timezone.utc).isoformat()
        _save(data)


def record_collaboration(source_worker_id: str, support_worker_id: str, *, task_type: str, success: bool, latency_ms: float | None = None) -> None:
    with _LOCK:
        data = _load()
        key = f"{source_worker_id}::{support_worker_id}"
        pair = data.setdefault("collaboration", {}).setdefault(key, {"source_worker_id": source_worker_id, "support_worker_id": support_worker_id, "observations": 0, "successes": 0, "failures": 0, "tasks": {}})
        pair["observations"] += 1; pair["successes"] += int(success); pair["failures"] += int(not success)
        task = pair.setdefault("tasks", {}).setdefault(task_type, {"observations": 0, "successes": 0, "failures": 0})
        task["observations"] += 1; task["successes"] += int(success); task["failures"] += int(not success)
        if latency_ms is not None: pair["last_latency_ms"] = round(float(latency_ms), 2)
        _save(data)


def get_worker_learning(worker_id: str) -> dict[str, Any]:
    with _LOCK: return _load().get("workers", {}).get(worker_id, {})


def task_performance(worker_id: str, task_type: str) -> dict[str, float]:
    worker = get_worker_learning(worker_id); task = worker.get("tasks", {}).get(task_type, {})
    observations = int(task.get("observations", 0))
    if not observations: return {"score": 0.0, "confidence": 0.0, "success_rate": 0.0, "rework_rate": 0.0, "avg_latency_ms": 0.0, "observations": 0}
    success_rate = task.get("successes", 0) / observations
    reviewed = int(task.get("quality_passes", 0)) + int(task.get("quality_reworks", 0))
    rework_rate = int(task.get("quality_reworks", 0)) / reviewed if reviewed else 0.0
    latencies = task.get("latencies_ms", []); avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    scores = task.get("quality_scores", []); quality = sum(scores) / len(scores) if scores else success_rate * 100
    score = max(0, min(100, quality*.55 + success_rate*100*.25 + (100-rework_rate*100)*.15 + max(0, min(100, 100-avg_latency/100))*.05))
    return {"score": round(score,2), "confidence": round(min(100, observations/20*100),2), "success_rate": round(success_rate*100,2), "rework_rate": round(rework_rate*100,2), "avg_latency_ms": round(avg_latency,2), "observations": observations}


def learned_adjustments(worker_id: str, task_type: str) -> dict[str, float]:
    p = task_performance(worker_id, task_type)
    if not p["observations"]: return {"reliability": 0.0, "efficiency": 0.0}
    return {"reliability": (p["success_rate"]-50)*.12, "efficiency": max(-5,min(5,(3000-p["avg_latency_ms"])/600))}


def learning_snapshot() -> dict[str, Any]:
    with _LOCK: return _load()


def _test_capability_for_worker(worker, capability: str) -> dict[str, Any]:
    tests = _CAPABILITY_TESTS.get(capability, [])
    return {"capability": capability, "test_count": len(tests), "tests": [{"test_id": t["id"], "metric": t["metric"], "prompt": t["prompt"], "status": "ready"} for t in tests]}


def self_initialize() -> dict[str, Any]:
    """Onboard only new workers. Existing onboarding and performance evidence is preserved."""
    from .worker_registry import list_workers
    now = datetime.now(timezone.utc).isoformat(); results = []
    with _LOCK:
        data = _load()
        for worker in list_workers():
            existing = data.setdefault("workers", {}).setdefault(worker.worker_id, _default_worker())
            if "onboarding" not in existing:
                caps = worker.capabilities.model_dump(exclude_none=True)
                applicable = [name for name, value in caps.items() if value is not None and name not in {"reliability", "efficiency", "instruction_following"}]
                existing["onboarding"] = {"status":"ready_for_benchmark", "initialized_at":now, "initial_capabilities":caps, "benchmark_capabilities":[_test_capability_for_worker(worker, c) for c in applicable], "tests_completed":0, "tests_total":sum(len(_CAPABILITY_TESTS.get(c, [])) for c in applicable), "note":"Initial capability scores are priors; actual task evidence progressively controls task-specific routing."}
                action = "new_worker_onboarding_created"
            else:
                action = "existing_worker_history_preserved"
            results.append({"worker_id":worker.worker_id,"action":action,"onboarding_status":existing["onboarding"]["status"],"observations":existing.get("observations",0),"tests_completed":existing["onboarding"].get("tests_completed",0),"tests_total":existing["onboarding"].get("tests_total",0)})
        _save(data)
    return {"status":"initialized","timestamp":now,"workers":results,"policy":"new_workers_get_benchmarks; existing_workers_keep_history"}
