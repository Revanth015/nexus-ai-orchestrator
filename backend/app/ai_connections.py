from __future__ import annotations

import json
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


def _public(item: dict[str, Any]) -> dict[str, Any]:
    # A configured API key is NOT enough to make an AI execution-ready.
    # NEXUS only exposes api_key_configured=True after a successful live test.
    return {
        k: v for k, v in item.items() if k != "api_key"
    } | {
        "api_key_configured": bool(item.get("api_key")) and item.get("test_status") == "ok"
    }


def list_connections() -> list[dict[str, Any]]:
    return [_public(item) for item in _load()["connections"]]


def get_connection(worker_id: str) -> dict[str, Any] | None:
    return next((x for x in _load()["connections"] if x["worker_id"] == worker_id), None)


def register_connection(*, name: str, provider: str, api_key: str, model: str,
                         base_url: str, free_verified: bool = False,
                         capabilities: dict[str, float] | None = None) -> dict[str, Any]:
    name, provider, api_key, model = name.strip(), provider.strip().lower(), api_key.strip(), model.strip()
    base_url = base_url.strip().rstrip("/")
    if not name or not provider or not api_key or not model or not base_url:
        raise ValueError("Name, provider, API key, model, and base URL are required.")

    default = {
        "reasoning": 75, "research": 75, "coding": 75, "documents": 75,
        "presentation": 70, "data_analysis": 70, "instruction_following": 80,
        "reliability": 70, "efficiency": 70,
    }
    worker_id = f"custom-{uuid4().hex[:10]}"
    item = {
        "worker_id": worker_id,
        "name": name,
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "free_verified": bool(free_verified),
        "capabilities": capabilities or default,
        "enabled": True,
        "test_status": "untested",
        "last_error": None,
        "last_latency_ms": None,
        "last_tested_at": None,
    }
    data = _load()
    data["connections"].append(item)
    _save(data)
    return _public(item)


def delete_connection(worker_id: str) -> bool:
    data = _load()
    before = len(data["connections"])
    data["connections"] = [x for x in data["connections"] if x["worker_id"] != worker_id]
    changed = len(data["connections"]) != before
    if changed:
        _save(data)
    return changed


def _post(url: str, key: str, payload: dict[str, Any], provider: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "http://localhost:5173"
        headers["X-Title"] = "NEXUS AI Corporate Manager"
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:1000]
        raise RuntimeError(f"{provider} returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach {provider}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"{provider} request timed out after 90 seconds") from exc


def _chat_url(item: dict[str, Any]) -> str:
    base = item["base_url"].rstrip("/")
    return base if base.endswith("/chat/completions") else f"{base}/chat/completions"


def _record_test(worker_id: str, status: str, *, error: str | None = None,
                 latency_ms: float | None = None) -> None:
    data = _load()
    item = next((x for x in data["connections"] if x["worker_id"] == worker_id), None)
    if item is None:
        return
    item["test_status"] = status
    item["last_error"] = error
    item["last_latency_ms"] = latency_ms
    item["last_tested_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save(data)


def test_connection(worker_id: str, prompt: str = "Reply with exactly: NEXUS connection is working.") -> dict[str, Any]:
    item = get_connection(worker_id)
    if not item:
        raise ValueError("AI connection not found.")
    if not item.get("api_key"):
        raise ValueError("API key is not configured.")

    started = time.perf_counter()
    try:
        data = _post(
            _chat_url(item),
            item["api_key"],
            {"model": item["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": 128},
            item["provider"],
        )
        choices = data.get("choices") or []
        text = (choices[0].get("message", {}).get("content", "") if choices else "").strip()
        if not text:
            raise RuntimeError("Provider returned no text content. Check the selected model and endpoint.")
        latency = round((time.perf_counter() - started) * 1000, 2)
        _record_test(worker_id, "ok", latency_ms=latency)
        return {"status": "ok", "text": text, "latency_ms": latency}
    except Exception as exc:
        error = str(exc)
        _record_test(worker_id, "failed", error=error, latency_ms=round((time.perf_counter() - started) * 1000, 2))
        raise RuntimeError(f"Connection test failed for {item['name']} ({item['provider']} / {item['model']}): {error}") from exc


def generate_custom(worker_id: str, prompt: str) -> dict[str, Any]:
    result = test_connection(worker_id, prompt)
    return {
        "text": result["text"],
        "telemetry": {
            "worker_id": worker_id,
            "last_latency_ms": result["latency_ms"],
            "configured": True,
            "execution_ready": True,
        },
    }
