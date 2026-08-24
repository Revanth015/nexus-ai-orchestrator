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
    return {k: v for k, v in item.items() if k != "api_key"} | {
        "api_key_configured": bool(item.get("api_key")),
        "connection_ready": item.get("test_status") == "ok",
        "execution_ready": bool(item.get("enabled", True)) and item.get("test_status") == "ok",
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
    default = {"reasoning": 75, "research": 75, "coding": 75, "documents": 75, "presentation": 70,
               "data_analysis": 70, "instruction_following": 80, "reliability": 70, "efficiency": 70}
    item = {"worker_id": f"custom-{uuid4().hex[:10]}", "name": name, "provider": provider, "api_key": api_key,
            "model": model, "base_url": base_url, "free_verified": bool(free_verified),
            "capabilities": capabilities or default, "enabled": True, "test_status": "untested",
            "last_error": None, "last_error_code": None, "last_error_status": None,
            "last_latency_ms": None, "last_tested_at": None, "last_diagnostic": None}
    data = _load(); data["connections"].append(item); _save(data)
    return _public(item)


def delete_connection(worker_id: str) -> bool:
    data = _load(); before = len(data["connections"])
    data["connections"] = [x for x in data["connections"] if x["worker_id"] != worker_id]
    changed = len(data["connections"]) != before
    if changed: _save(data)
    return changed


def _url(item: dict[str, Any], path: str) -> str:
    base = item["base_url"].rstrip("/")
    if base.endswith(path.lstrip("/")):
        return base
    return f"{base}/{path.lstrip('/')}"


def _request(url: str, key: str, method: str = "GET", payload: dict[str, Any] | None = None,
             provider: str = "") -> tuple[int, dict[str, Any] | str]:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "http://localhost:5173"
        headers["X-Title"] = "NEXUS AI Corporate Manager"
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode(errors="replace")
            try: return response.status, json.loads(raw or "{}")
            except json.JSONDecodeError: return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")[:2000]
        try: body = json.loads(raw or "{}")
        except json.JSONDecodeError: body = raw
        return exc.code, body
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Request timed out after 30 seconds") from exc


def _error_details(body: dict[str, Any] | str) -> tuple[str | None, str]:
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            return str(error.get("code")) if error.get("code") is not None else None, str(error.get("message") or body)
    return None, str(body)


def _record_test(worker_id: str, status: str, *, error: str | None = None, error_code: str | None = None,
                error_status: int | None = None, latency_ms: float | None = None,
                diagnostic: dict[str, Any] | None = None) -> None:
    data = _load(); item = next((x for x in data["connections"] if x["worker_id"] == worker_id), None)
    if item is None: return
    item.update({"test_status": status, "last_error": error, "last_error_code": error_code,
                 "last_error_status": error_status, "last_latency_ms": latency_ms,
                 "last_tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "last_diagnostic": diagnostic})
    _save(data)


def diagnose_connection(worker_id: str) -> dict[str, Any]:
    item = get_connection(worker_id)
    if not item: raise ValueError("AI connection not found.")
    if not item.get("api_key"): raise ValueError("API key is not configured.")
    provider, base = item["provider"], item["base_url"].rstrip("/")
    result = {"provider": provider, "model": item["model"], "base_url": base,
              "endpoint": {"status": "not_tested"}, "authentication": {"status": "not_tested"},
              "model": {"status": "not_tested", "name": item["model"]},
              "completion": {"status": "not_tested"}, "overall": "failed", "latency_ms": None}
    started = time.perf_counter()

    # OpenAI-compatible providers expose a model catalogue. This separates endpoint/key
    # failures from model-name failures before attempting a completion.
    try:
        status, body = _request(f"{base}/models", item["api_key"], provider=provider)
        if status == 200:
            result["endpoint"] = {"status": "pass", "http_status": status}
            result["authentication"] = {"status": "pass"}
            models = body.get("data", []) if isinstance(body, dict) else []
            ids = [m.get("id") for m in models if isinstance(m, dict)]
            result["model"]["available"] = item["model"] in ids
            result["model"]["status"] = "pass" if item["model"] in ids else "fail"
            if item["model"] not in ids:
                result["model"]["available_models_sample"] = ids[:25]
        else:
            code, message = _error_details(body)
            result["endpoint"] = {"status": "pass", "http_status": status, "note": "Provider endpoint responded."}
            result["authentication"] = {"status": "fail", "http_status": status, "code": code, "message": message}
            result["overall"] = "failed"
            return _finalize_diagnostic(item, result, started, message, code, status)
    except Exception as exc:
        result["endpoint"] = {"status": "fail", "message": str(exc)}
        return _finalize_diagnostic(item, result, started, str(exc), None, None)

    if result["model"]["status"] != "pass":
        message = f"Model '{item['model']}' is not available from the provider's /models response."
        return _finalize_diagnostic(item, result, started, message, "model_unavailable", 200)

    # Only now test an actual completion.
    try:
        status, body = _request(_url(item, "chat/completions"), item["api_key"], method="POST",
                                payload={"model": item["model"], "messages": [{"role": "user", "content": "Reply with exactly: NEXUS connection is working."}], "max_tokens": 128}, provider=provider)
        if status != 200:
            code, message = _error_details(body)
            result["completion"] = {"status": "fail", "http_status": status, "code": code, "message": message}
            return _finalize_diagnostic(item, result, started, message, code, status)
        choices = body.get("choices") or [] if isinstance(body, dict) else []
        text = (choices[0].get("message", {}).get("content", "") if choices else "").strip()
        if not text: raise RuntimeError("Completion endpoint returned no text content.")
        result["completion"] = {"status": "pass", "response_preview": text[:200]}
        result["overall"] = "ok"
        return _finalize_diagnostic(item, result, started, None, None, 200)
    except Exception as exc:
        return _finalize_diagnostic(item, result, started, str(exc), None, None)


def _finalize_diagnostic(item: dict[str, Any], result: dict[str, Any], started: float,
                         error: str | None, code: str | None, status: int | None) -> dict[str, Any]:
    latency = round((time.perf_counter() - started) * 1000, 2)
    result["latency_ms"] = latency
    if error:
        result["error"] = {"status": status, "code": code, "message": error}
        _record_test(item["worker_id"], "failed", error=error, error_code=code,
                     error_status=status, latency_ms=latency, diagnostic=result)
        raise RuntimeError(json.dumps(result))
    _record_test(item["worker_id"], "ok", latency_ms=latency, diagnostic=result)
    return result


def test_connection(worker_id: str, prompt: str = "Reply with exactly: NEXUS connection is working.") -> dict[str, Any]:
    # Keep the existing public operation, but return the richer diagnostic contract.
    return diagnose_connection(worker_id)


def generate_custom(worker_id: str, prompt: str) -> dict[str, Any]:
    item = get_connection(worker_id)
    if not item: raise ValueError("AI connection not found.")
    if item.get("test_status") != "ok":
        raise RuntimeError("AI employee is not connection-ready. Run a successful connection diagnostic first.")
    started = time.perf_counter()
    status, body = _request(_url(item, "chat/completions"), item["api_key"], method="POST",
                            payload={"model": item["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024}, provider=item["provider"])
    if status != 200:
        code, message = _error_details(body)
        _record_test(worker_id, "failed", error=message, error_code=code, error_status=status,
                     latency_ms=round((time.perf_counter()-started)*1000,2))
        raise RuntimeError(f"Execution failed: HTTP {status} [{code}] {message}")
    choices = body.get("choices") or []
    text = (choices[0].get("message", {}).get("content", "") if choices else "").strip()
    if not text: raise RuntimeError("Provider returned no text content.")
    latency = round((time.perf_counter()-started)*1000,2)
    return {"text": text, "telemetry": {"worker_id": worker_id, "last_latency_ms": latency, "configured": True, "execution_ready": True}}
