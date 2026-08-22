from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

_STORE = Path(__file__).resolve().parent.parent / ".nexus_audit_log.json"
_LOCK = Lock()


def _load() -> list[dict[str, Any]]:
    try:
        value = json.loads(_STORE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(events: list[dict[str, Any]]) -> None:
    _STORE.write_text(json.dumps(events[-5000:], indent=2), encoding="utf-8")


def record_event(event_type: str, *, mission_id: str | None = None, task_id: str | None = None, actor: str = "nexus-manager", data: dict[str, Any] | None = None) -> dict[str, Any]:
    event = {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "mission_id": mission_id,
        "task_id": task_id,
        "actor": actor,
        "data": data or {},
    }
    with _LOCK:
        events = _load()
        events.append(event)
        _save(events)
    return event


def list_events(*, mission_id: str | None = None, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 500))
    with _LOCK:
        events = _load()
    if mission_id is not None:
        events = [e for e in events if e.get("mission_id") == mission_id]
    if task_id is not None:
        events = [e for e in events if e.get("task_id") == task_id]
    return events[-limit:]


def decision_record(*, mission_id: str, task_id: str, task_type: str, selected_worker_id: str | None, candidates: list[dict[str, Any]], decision: str, rationale: str, confidence: float, expected_value: float, resource_cost: float) -> dict[str, Any]:
    return record_event("manager_decision", mission_id=mission_id, task_id=task_id, data={
        "task_type": task_type,
        "selected_worker_id": selected_worker_id,
        "candidates": candidates,
        "decision": decision,
        "rationale": rationale,
        "confidence": confidence,
        "expected_value": expected_value,
        "resource_cost": resource_cost,
    })


def mission_summary(mission_id: str) -> dict[str, Any]:
    events = list_events(mission_id=mission_id, limit=500)
    decisions = [e for e in events if e["event_type"] == "manager_decision"]
    reworks = [e for e in events if e["event_type"] == "qa_rework"]
    return {
        "mission_id": mission_id,
        "event_count": len(events),
        "decision_count": len(decisions),
        "rework_count": len(reworks),
        "events": events,
    }
