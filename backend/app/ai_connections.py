from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4

_STORE = Path(__file__).resolve().parent.parent / ".nexus_ai_connections.json"


def _load():
    try:
        data = json.loads(_STORE.read_text(encoding="utf-8"))
        data.setdefault("connections", [])
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"connections": []}


def _save(data):
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".nexus_ai_connections_", suffix=".tmp", dir=_STORE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, _STORE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _public(x):
    public = {k: v for k, v in x.items() if k != "api_key"}
    public.update({
        "api_key_configured": bool(x.get("api_key")),
        "connection_ready": x.get("test_status") == "ok",
        "execution_ready": bool(x.get("enabled", True)) and x.get("test_status") == "ok",
        "free_status": "user_declared_free" if x.get("free_verified") else "unknown",
    })
    return public


def list_connections():
    return [_public(x) for x in _load()["connections"]]


def get_connection(worker_id):
    return next((x for x in _load()["connections"] if x["worker_id"] == worker_id), None)


def _validate_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL must be a valid http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise ValueError("Base URL must not contain embedded credentials.")
    hostname = (parsed.hostname or "").lower()
    blocked = {"169.254.169.254", "metadata.google.internal", "metadata.azure.internal"}
    if hostname in blocked:
        raise ValueError("Base URL points to a blocked cloud metadata endpoint.")
    return value


def register_connection(*, name, provider, api_key, model, base_url, free_verified=False, capabilities=None):
    name, provider, api_key, model = name.strip(), provider.strip().lower(), api_key.strip(), model.strip()
    base_url = _validate_base_url(base_url)
    if not all((name, provider, api_key, model, base_url)):
        raise ValueError("Name, provider, API key, model, and base URL are required.")
    default = {"reasoning": 75, "research": 75, "coding": 75, "documents": 75, "presentation": 70, "data_analysis": 70, "instruction_following": 80, "reliability": 70, "efficiency": 70}
    item = {
        "worker_id": f"custom-{uuid4().hex[:10]}", "name": name, "provider": provider, "api_key": api_key,
        "model": model, "base_url": base_url, "free_verified": bool(free_verified),
        "capabilities": capabilities or default, "enabled": True, "test_status": "untested",
        "last_error": None, "last_error_code": None, "last_error_status": None,
        "last_latency_ms": None, "last_tested_at": None, "last_diagnostic": None,
        "config_revision": 1,
    }
    data = _load(); data["connections"].append(item); _save(data)
    return _public(item)


def update_connection(worker_id, *, name, provider, api_key=None, model=None, base_url=None, free_verified=None, capabilities=None, enabled=None):
    data = _load(); item = next((x for x in data["connections"] if x["worker_id"] == worker_id), None)
    if not item:
        raise ValueError("Custom AI employee not found.")
    if name is not None: item["name"] = name.strip()
    if provider is not None: item["provider"] = provider.strip().lower()
    if api_key is not None and api_key.strip(): item["api_key"] = api_key.strip()
    if model is not None: item["model"] = model.strip()
    if base_url is not None: item["base_url"] = _validate_base_url(base_url)
    if free_verified is not None: item["free_verified"] = bool(free_verified)
    if capabilities is not None: item["capabilities"] = capabilities
    if enabled is not None: item["enabled"] = bool(enabled)
    if not all((item.get("name"), item.get("provider"), item.get("api_key"), item.get("model"), item.get("base_url"))):
        raise ValueError("Name, provider, API key, model, and base URL are required.")
    # Any configuration change invalidates the previous successful connection test.
    item["test_status"] = "untested"
    item["last_error"] = None; item["last_error_code"] = None; item["last_error_status"] = None
    item["last_diagnostic"] = None; item["last_tested_at"] = None
    item["config_revision"] = int(item.get("config_revision", 0)) + 1
    _save(data)
    return _public(item)


def delete_connection(worker_id):
    data = _load(); before = len(data["connections"])
    data["connections"] = [x for x in data["connections"] if x["worker_id"] != worker_id]
    changed = len(data["connections"]) != before
    if changed: _save(data)
    return changed


def _url(item, path):
    return f'{item["base_url"].rstrip("/")}/{path.lstrip("/")}'


def _request(url, key, method="GET", payload=None, provider=""):
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "NEXUS/0.2"}
    if provider == "openrouter": headers.update({"HTTP-Referer": "http://localhost:5173", "X-Title": "NEXUS AI Corporate Manager"})
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode(errors="replace")
            try: return r.status, json.loads(raw or "{}")
            except json.JSONDecodeError: return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")[:4000]
        try: body = json.loads(raw or "{}")
        except json.JSONDecodeError: body = raw
        return e.code, body
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e
    except TimeoutError as e:
        raise RuntimeError("Request timed out after 30 seconds") from e


def _error_details(body):
    if isinstance(body, dict):
        e = body.get("error", body)
        if isinstance(e, dict): return (str(e.get("code")) if e.get("code") is not None else None), str(e.get("message") or e)
    return None, str(body)


def _record(worker_id, status, diagnostic=None, error=None, code=None, http_status=None, latency=None):
    data = _load(); item = next((x for x in data["connections"] if x["worker_id"] == worker_id), None)
    if not item: return
    item.update({"test_status": status, "last_error": error, "last_error_code": code, "last_error_status": http_status, "last_latency_ms": latency, "last_tested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "last_diagnostic": diagnostic})
    _save(data)


def _result(provider, model, base):
    return {"provider": provider, "model_name": model, "base_url": base, "endpoint": "NOT_TESTED", "authentication": "NOT_TESTED", "model_status": "NOT_TESTED", "completion_status": "NOT_TESTED", "http_status": None, "latency_ms": None, "overall": "FAIL", "error": None, "details": {}}


def _finish(item, result, started, error=None, code=None, http_status=None):
    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2); result["http_status"] = http_status
    if error:
        result["error"] = str(error); result["details"]["error"] = {"message": str(error), "code": code, "http_status": http_status}
    ok = result["overall"] == "PASS" and not error
    _record(item["worker_id"], "ok" if ok else "failed", result, str(error) if error else None, code, http_status, result["latency_ms"])
    return result


def _extract_completion_text(body):
    if not isinstance(body, dict): return ""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices: return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict): return ""
    content = message.get("content")
    if isinstance(content, str) and content.strip(): return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str) and text.strip(): parts.append(text.strip())
            elif isinstance(part, str) and part.strip(): parts.append(part.strip())
        if parts: return "\n".join(parts)
    # Only use reasoning when no final content exists. Reasoning is never preferred over final answer content.
    reasoning = message.get("reasoning")
    return reasoning.strip() if isinstance(reasoning, str) and reasoning.strip() else ""


def diagnose_connection(worker_id, prompt="Reply with exactly: NEXUS connection is working."):
    item = get_connection(worker_id)
    if not item: raise ValueError("AI connection not found.")
    if not item.get("api_key"): raise ValueError("API key is not configured.")
    started = time.perf_counter(); base = item["base_url"].rstrip("/"); model = item["model"]; provider = item["provider"]; result = _result(provider, model, base); result["endpoint"] = "PASS"
    try:
        status, body = _request(_url(item, "chat/completions"), item["api_key"], "POST", {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 32, "temperature": 0}, provider)
        result["http_status"] = status
        if status != 200:
            code, msg = _error_details(body); result["authentication"] = "FAIL" if status in (401, 403) else "NOT_TESTED"; result["completion_status"] = "FAIL"; result["details"]["provider_code"] = code
            return _finish(item, result, started, msg, code, status)
        result["authentication"] = "PASS"; result["model_status"] = "PASS"; text = _extract_completion_text(body)
        if not text:
            result["completion_status"] = "FAIL"; result["details"]["response_shape"] = {"top_level_keys": list(body.keys()) if isinstance(body, dict) else [], "choices_count": len(body.get("choices", [])) if isinstance(body, dict) and isinstance(body.get("choices"), list) else 0}
            return _finish(item, result, started, "Completion endpoint returned no usable final text content.")
        result["completion_status"] = "PASS"; result["details"]["response_preview"] = text[:200]; result["overall"] = "PASS"
        return _finish(item, result, started)
    except Exception as e:
        return _finish(item, result, started, str(e))


def test_connection(worker_id, prompt="Reply with exactly: NEXUS connection is working."):
    return diagnose_connection(worker_id, prompt=prompt)


def generate_custom(worker_id, prompt):
    item = get_connection(worker_id)
    if not item: raise ValueError("AI connection not found.")
    if item.get("test_status") != "ok": raise RuntimeError("AI employee is not connection-ready. Run a successful connection diagnostic first.")
    started = time.perf_counter()
    status, body = _request(_url(item, "chat/completions"), item["api_key"], "POST", {"model": item["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024}, item["provider"])
    latency = round((time.perf_counter() - started) * 1000, 2)
    if status != 200:
        code, msg = _error_details(body); _record(worker_id, "failed", error=msg, code=code, http_status=status, latency=latency)
        raise RuntimeError(f"Execution failed: HTTP {status} [{code}] {msg}")
    text = _extract_completion_text(body)
    if not text:
        _record(worker_id, "failed", error="Provider returned no usable final text content.", latency=latency)
        raise RuntimeError("Provider returned no usable final text content.")
    return {"text": text, "telemetry": {"worker_id": worker_id, "last_latency_ms": latency, "configured": True, "execution_ready": True, "free_status": "user_declared_free" if item.get("free_verified") else "unknown"}}
