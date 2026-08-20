from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import re
import time
from typing import Any

from pydantic import BaseModel, Field


# Current free-tier text model selected for the first NEXUS connector.
# Google lists Gemini 3.5 Flash-Lite as free of charge on the Free Tier.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
FREE_VERIFIED_MODELS = {DEFAULT_MODEL, "gemini-3.1-flash-lite"}


@dataclass
class GeminiRuntime:
    configured: bool = False
    execution_ready: bool = False
    observed_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_error: str | None = None
    last_latency_ms: float | None = None
    quota_status: str = "unknown"
    quota_estimate: float | None = None
    failure_class: str | None = None
    _recent_results: list[bool] = field(default_factory=list)

    def record_success(self, latency_ms: float) -> None:
        self.observed_requests += 1
        self.successful_requests += 1
        self.last_success_at = _now()
        self.last_latency_ms = round(latency_ms, 2)
        self.last_error = None
        self.failure_class = None
        self._recent_results.append(True)
        self._recent_results = self._recent_results[-20:]
        self.execution_ready = True
        # Never infer an exact remaining quota from a successful request.
        self.quota_status = "unknown"
        self.quota_estimate = None

    def record_failure(self, error: str, failure_class: str, latency_ms: float) -> None:
        self.observed_requests += 1
        self.failed_requests += 1
        self.last_failure_at = _now()
        self.last_latency_ms = round(latency_ms, 2)
        self.last_error = error[:500]
        self.failure_class = failure_class
        self._recent_results.append(False)
        self._recent_results = self._recent_results[-20:]
        self.execution_ready = False
        if failure_class in {"quota", "rate_limit"}:
            self.quota_status = "exhausted_or_limited"
        else:
            self.quota_status = "unknown"
        self.quota_estimate = None


_RUNTIME = GeminiRuntime()


class GeminiTestRequest(BaseModel):
    prompt: str = Field(
        default="Reply with exactly: NEXUS Gemini connector is working.",
        min_length=1,
        max_length=4000,
    )


class GeminiStatus(BaseModel):
    provider: str = "google"
    worker_id: str = "gemini"
    model: str
    configured: bool
    execution_ready: bool
    free_only: bool = True
    free_model_verified: bool
    quota_status: str
    quota_exact: float | None = None
    quota_estimate: float | None = None
    observed_requests: int
    successful_requests: int
    failed_requests: int
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_latency_ms: float | None = None
    failure_class: str | None = None
    last_error: str | None = None
    note: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model() -> str:
    return os.getenv("NEXUS_GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _classify_error(error: Exception) -> str:
    text = str(error).lower()
    status = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status in {401, 403} or any(
        term in text
        for term in ("api key", "authentication", "unauthenticated", "permission denied", "forbidden")
    ):
        return "authentication"
    if status == 429 or any(
        term in text
        for term in ("quota", "rate limit", "resource exhausted", "too many requests", "429")
    ):
        return "quota" if "quota" in text or "resource exhausted" in text else "rate_limit"
    if status in {408, 500, 502, 503, 504} or any(
        term in text for term in ("timeout", "temporarily unavailable", "service unavailable")
    ):
        return "temporary"
    return "provider_error"


def _clean_error(error: Exception) -> str:
    text = re.sub(
        r"(?:api[_ -]?key|key)\s*[:=]\s*['\"]?[^\s'\"]+",
        "API_KEY=[REDACTED]",
        str(error),
        flags=re.IGNORECASE,
    )
    return text[:500]


def status() -> GeminiStatus:
    model = _model()
    configured = bool(_api_key())
    _RUNTIME.configured = configured
    free_verified = model in FREE_VERIFIED_MODELS
    return GeminiStatus(
        model=model,
        configured=configured,
        execution_ready=_RUNTIME.execution_ready and configured and free_verified,
        free_model_verified=free_verified,
        quota_status=_RUNTIME.quota_status,
        quota_estimate=_RUNTIME.quota_estimate,
        observed_requests=_RUNTIME.observed_requests,
        successful_requests=_RUNTIME.successful_requests,
        failed_requests=_RUNTIME.failed_requests,
        last_success_at=_RUNTIME.last_success_at,
        last_failure_at=_RUNTIME.last_failure_at,
        last_latency_ms=_RUNTIME.last_latency_ms,
        failure_class=_RUNTIME.failure_class,
        last_error=_RUNTIME.last_error,
        note=(
            "Exact remaining quota is not claimed. NEXUS records observed telemetry and provider limit errors."
            if configured
            else "Set GEMINI_API_KEY locally, then run the connector test. No key is stored in Git."
        ),
    )


def generate_text(prompt: str) -> dict[str, Any]:
    model = _model()
    if model not in FREE_VERIFIED_MODELS:
        raise ValueError(
            f"Model '{model}' is not in NEXUS's verified-free allowlist. "
            f"Use {DEFAULT_MODEL} for free-only Stage 5 testing."
        )

    api_key = _api_key()
    if not api_key:
        raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY locally.")

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("Gemini SDK is not installed. Run: pip install -r requirements.txt") from exc

    started = time.perf_counter()
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        text = (response.text or "").strip()
        latency_ms = (time.perf_counter() - started) * 1000
        _RUNTIME.record_success(latency_ms)
        return {
            "provider": "google",
            "worker_id": "gemini",
            "model": model,
            "text": text,
            "latency_ms": round(latency_ms, 2),
            "telemetry": status().model_dump(),
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        failure_class = _classify_error(exc)
        _RUNTIME.record_failure(_clean_error(exc), failure_class, latency_ms)
        raise RuntimeError(f"Gemini connector failed ({failure_class}): {_clean_error(exc)}") from exc


def test_connection(prompt: str) -> dict[str, Any]:
    return generate_text(prompt)


def runtime_metadata() -> dict[str, Any]:
    current = status()
    return {
        "connected": current.execution_ready,
        "execution_ready": current.execution_ready,
        "configured": current.configured,
        "model": current.model,
        "quota_status": current.quota_status,
        "quota_known": False,
        "estimated_remaining": None,
        "observed_requests": current.observed_requests,
        "last_error": current.last_error,
    }
