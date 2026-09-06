from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ResponseQuality:
    passed: bool
    reason: str


_ERROR_PATTERNS = (
    r"\bapi[_ -]?key (?:is )?not configured\b",
    r"\bconnector failed\b",
    r"\bexecution failed\b",
    r"\bno execution[- ]ready worker\b",
    r"\bservice unavailable\b",
    r"\brate limit(?:ed)?\b",
    r"\bresource exhausted\b",
    r"\binternal server error\b",
)


def assess_response(task_type: str, prompt: str, output: str) -> ResponseQuality:
    """Apply conservative, deterministic checks before accepting a worker response.

    This is intentionally not a factuality judge. It only catches responses that are
    clearly unusable because the worker returned nothing, an obvious execution error,
    or a placeholder instead of an answer. Legitimate clarification requests remain
    valid responses.
    """
    text = str(output or "").strip()
    if not text:
        return ResponseQuality(False, "Worker returned an empty response.")

    if len(text) < 12:
        return ResponseQuality(False, "Worker response is too short to be usable.")

    lowered = text.lower()
    for pattern in _ERROR_PATTERNS:
        if re.search(pattern, lowered):
            return ResponseQuality(False, f"Worker returned an execution-error response ({pattern}).")

    placeholder_patterns = (
        "[no response]",
        "[empty response]",
        "placeholder response",
        "todo: provide answer",
    )
    if lowered in placeholder_patterns:
        return ResponseQuality(False, "Worker returned a placeholder response.")

    return ResponseQuality(True, "Response passed basic usability checks.")
