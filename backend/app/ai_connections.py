from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

_STORE = Path(__file__).resolve().parent.parent / ".nexus_ai_connections.json"


def _load() -> dict[str, Any]:
    try:
        data = json.loads(_STORE.read_text(encoding="utf-8"))
        data.setdefault("connections", [])
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"connections": []}


def _save(data: dict[str, Any]) -> None:
    _STORE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_connections() -> list[dict[str, Any]]:
    return [
        {k: v for k, v in item.items() if k != "api_key"}
        | {"api_key_configured": bool(item.get("api_key"))}
        for item in _load()["connections"]
    ]


def get_connection(worker_id: str) -> dict[str, Any] | None:
    return next((x for x in _load()["connections"] if x["worker_id"] == worker_id), None)


def register_connection(*, name: str, provider: str, api_key: str, model: str, base_url: str, free_verified: bool = False, capabilities: dict[str, float] | None = None) -> dict[str, Any]:
    name = name.strip(); provider = provider.strip().lower(); api_key = api_key.strip(); model = model.strip(); base_url = base_url.strip().rstrip("/")
    if not name or not provider or not api_key or not model or not base_url:
        raise ValueError("Name, provider, API key, model, and base URL are required.")
    data = _load()
    worker_id = f"custom-{uuid4().hex[:10]}"
    item = {
        "worker_id": worker_id, "name": name, "provider": provider, "api_key": api_key,
        "model": model, "base_url": base_url, "free_verified": bool(free_verified),
        "capabilities": capabilities or {}, "enabled": True,
    }
    data["connections"].append(item); _save(data)
    return {k: v for k, v in item.items() if k != "api_key"} | {"api_key_configured": True}


def delete_connection(worker_id: str) -> bool:
    data = _load(); before = len(data["connections"])
    data["connections"] = [x for x in data["connections"] if x["worker_id"] != worker_id]
    if len(data["connections"]) == before: return False
    _save(data); return True


def _post(url: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read().decode("utf-8"); return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc


def test_connection(worker_id: str, prompt: str = "Reply with exactly: NEXUS connection is working.") -> dict[str, Any]:
    item = get_connection(worker_id)
    if not item: raise ValueError("AI connection not found.")
    if not item.get("api_key"): raise ValueError("API key is not configured.")
    started = time.perf_counter()
    try:
        url = item["base_url"]
        if not url.endswith("/chat/completions"): url += "/chat/completions"
        data = _post(url, item["api_key"], {"model": item["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": 128})
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not text: raise RuntimeError("Provider returned no text content.")
        return {"status": "ok", "text": text, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
    except Exception as exc:
        raise RuntimeError(f"Connection test failed: {exc}") from exc


def generate_custom(worker_id: str, prompt: str) -> dict[str, Any]:
    result = test_connection(worker_id, prompt)
    return {"text": result["text"], "telemetry": {"worker_id": worker_id, "last_latency_ms": result["latency_ms"], "configured": True, "execution_ready": True}}
