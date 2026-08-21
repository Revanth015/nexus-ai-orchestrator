from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

_STATE: dict[str, dict[str, Any]] = {
    "claude": {"observed_requests": 0, "successful_requests": 0, "failed_requests": 0, "last_success_at": None, "last_failure_at": None, "last_latency_ms": None, "last_error": None},
    "perplexity": {"observed_requests": 0, "successful_requests": 0, "failed_requests": 0, "last_success_at": None, "last_failure_at": None, "last_latency_ms": None, "last_error": None},
}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _post(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"error": raw}
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _record(worker_id: str, ok: bool, latency: float, error: str | None = None) -> None:
    state = _STATE[worker_id]
    state["observed_requests"] += 1
    state["last_latency_ms"] = latency
    if ok:
        state["successful_requests"] += 1
        state["last_success_at"] = _now()
        state["last_failure_at"] = None
        state["last_error"] = None
    else:
        state["failed_requests"] += 1
        state["last_failure_at"] = _now()
        state["last_error"] = error


def _status(worker_id: str, provider: str, model: str, configured: bool, free_verified: bool) -> dict[str, Any]:
    state = _STATE[worker_id]
    ready = state["successful_requests"] > 0 and state["last_failure_at"] is None and free_verified
    return {
        "provider": provider, "worker_id": worker_id, "model": model, "configured": configured,
        "execution_ready": ready, "free_only": True, "free_model_verified": free_verified,
        "quota_status": "unknown", "quota_exact": None, "quota_estimate": None, **state,
        "note": "NEXUS only routes this provider in free-only mode when its free eligibility is explicitly verified. API availability alone is not treated as free.",
    }


def claude_status() -> dict[str, Any]:
    return _status("claude", "anthropic", os.getenv("CLAUDE_MODEL", "claude-3-5-haiku-latest"), bool(os.getenv("ANTHROPIC_API_KEY", "").strip()), os.getenv("CLAUDE_FREE_VERIFIED", "false").lower() == "true")


def perplexity_status() -> dict[str, Any]:
    return _status("perplexity", "perplexity", os.getenv("PERPLEXITY_MODEL", "sonar"), bool(os.getenv("PERPLEXITY_API_KEY", "").strip()), os.getenv("PERPLEXITY_FREE_VERIFIED", "false").lower() == "true")


def generate_claude(prompt: str) -> dict[str, Any]:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    model = os.getenv("CLAUDE_MODEL", "claude-3-5-haiku-latest")
    if not key:
        raise RuntimeError("Claude connector is not configured. Set ANTHROPIC_API_KEY locally.")
    started = time.perf_counter()
    try:
        data = _post("https://api.anthropic.com/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01"}, {"model": model, "max_tokens": 2048, "messages": [{"role": "user", "content": prompt}]})
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()
        if not text:
            raise RuntimeError("Claude returned no text content.")
        latency = round((time.perf_counter() - started) * 1000, 2)
        _record("claude", True, latency)
        return {"text": text, "telemetry": claude_status()}
    except Exception as exc:
        latency = round((time.perf_counter() - started) * 1000, 2)
        _record("claude", False, latency, str(exc))
        raise RuntimeError(f"Claude connector failed: {exc}") from exc


def generate_perplexity(prompt: str) -> dict[str, Any]:
    key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    model = os.getenv("PERPLEXITY_MODEL", "sonar")
    if not key:
        raise RuntimeError("Perplexity connector is not configured. Set PERPLEXITY_API_KEY locally.")
    started = time.perf_counter()
    try:
        data = _post("https://api.perplexity.ai/chat/completions", {"Authorization": f"Bearer {key}"}, {"model": model, "messages": [{"role": "user", "content": prompt}]})
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not text:
            raise RuntimeError("Perplexity returned no text content.")
        latency = round((time.perf_counter() - started) * 1000, 2)
        _record("perplexity", True, latency)
        return {"text": text, "telemetry": perplexity_status()}
    except Exception as exc:
        latency = round((time.perf_counter() - started) * 1000, 2)
        _record("perplexity", False, latency, str(exc))
        raise RuntimeError(f"Perplexity connector failed: {exc}") from exc


def test_claude(prompt: str = "Reply with exactly: NEXUS Claude connector is working.") -> dict[str, Any]:
    return generate_claude(prompt)


def test_perplexity(prompt: str = "Reply with exactly: NEXUS Perplexity connector is working.") -> dict[str, Any]:
    return generate_perplexity(prompt)
