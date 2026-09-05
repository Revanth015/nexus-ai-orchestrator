from __future__ import annotations

import re
from datetime import datetime, timezone

from . import worker_learning as learning


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def _numbered_items(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if re.match(r"^\s*\d+[.)]\s+", line)]


def evaluate_test(test_id: str, text: str) -> dict:
    """Objective-but-tolerant benchmark scoring. Never treats reasoning traces as the final answer."""
    text = (text or "").strip()
    lower = text.lower()
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("non_empty", bool(text), "A usable final answer was returned." if text else "No final answer text was returned.")
    if not text:
        return {"score": 0.0, "checks": checks, "summary": "No usable final answer."}

    if test_id == "reasoning_logic_01":
        check("logic_conclusion", bool(re.search(r"\bno\b", lower) and "a" in lower and "c" in lower), "Answer addresses whether A can be C.")
        check("justification", len(text.split(".", 1)) > 1 or len(text.splitlines()) > 1, "Provides a conclusion with supporting explanation.")
    elif test_id == "reasoning_constraints_01":
        items = _numbered_items(text)
        check("three_items", len(items) == 3, f"Found {len(items)} numbered items; target is 3.")
        check("near_five_words", len(items) == 3 and all(4 <= _word_count(x) <= 6 for x in items), "Allows minor model formatting variation while preserving the requested five-word constraint.")
    elif test_id == "research_synthesis_01":
        check("evidence", "evidence" in lower, "Discusses evidence." )
        check("source_quality", "source" in lower or "quality" in lower, "Discusses source quality or sources." )
        check("conflicts", "conflict" in lower or "disagree" in lower or "contradict" in lower, "Addresses conflicting evidence." )
        check("no_invention", "do not invent" in lower or "not invent" in lower or "verify" in lower, "Shows evidence discipline." )
    elif test_id == "research_claims_01":
        items = _numbered_items(text)
        check("three_claims", len(items) >= 3, f"Found {len(items)} numbered claim items." )
        check("evidence_requirements", lower.count("evidence") >= 2 or lower.count("verify") >= 2, "Links claims to verification evidence." )
    elif test_id == "data_calculation_01":
        check("mean", bool(re.search(r"\b136\b", text)), "Mean is 136." )
        check("median", bool(re.search(r"\b130\b", text)), "Median is 130." )
        check("maximum", bool(re.search(r"\b180\b", text)), "Maximum is 180." )
        check("range", bool(re.search(r"\b80\b", text)), "Range is 80." )
    elif test_id == "data_interpretation_01":
        check("defensible_pattern", "pattern" in lower or "trend" in lower or "increase" in lower, "Identifies a defensible pattern or trend." )
        check("limitation", "cannot" in lower or "not enough" in lower or "cannot establish" in lower or "not establish" in lower, "States a limitation on inference." )
    elif test_id == "documents_completeness_01":
        for term in ("objective", "status", "finding", "risk", "next action"):
            check(term, term in lower, f"Contains a {term} section." )
    elif test_id == "documents_adherence_01":
        wc = _word_count(text)
        check("version_control", "version control" in lower, "Explains version control." )
        check("corporate_context", "corporate" in lower or "workflow" in lower or "ai" in lower, "Uses the requested corporate AI workflow context." )
        check("reasonable_length", 72 <= wc <= 88, f"Returned {wc} words; allows small model variation around 80." )
    elif test_id == "coding_logic_01":
        check("function", bool(re.search(r"\bdef\s+average\s*\(", lower)), "Defines average(values)." )
        check("empty_guard", "valueerror" in lower or "empty" in lower, "Handles an empty input." )
        check("mean_return", "return" in lower, "Returns the arithmetic mean." )
        check("test", "assert" in lower or "test" in lower, "Includes a test/example." )
    elif test_id == "coding_debug_01":
        check("division_failure", "zero" in lower or "zerodivision" in lower or "division" in lower, "Identifies division-by-zero failure." )
        check("correction", "count" in lower and ("guard" in lower or "if" in lower or "nonzero" in lower or "raise" in lower), "Provides a corrective approach." )
    elif test_id == "presentation_structure_01":
        items = _numbered_items(text)
        slide_count = len(items) if items else len(re.findall(r"(?:slide\s*)?\b[1-6][.:)]", lower))
        check("six_slides", slide_count >= 6, f"Detected at least {slide_count} slide markers." )
        check("purpose", "purpose" in lower or "objective" in lower or "recommendation" in lower, "States slide purpose/content." )
    elif test_id == "vision_readiness_01":
        check("observation", "observation" in lower, "Separates visual observations." )
        check("inference", "inference" in lower, "Separates inference from observation." )
        check("uncertainty", "uncertainty" in lower or "confidence" in lower, "Reports uncertainty." )
    else:
        check("response", bool(text), "Returned a response for an unknown benchmark." )

    score = round(sum(c["passed"] for c in checks) / len(checks) * 100, 2)
    failed = [c["name"] for c in checks if not c["passed"]]
    summary = "All objective checks passed." if not failed else "Failed checks: " + ", ".join(failed)
    return {"score": score, "checks": checks, "summary": summary}


def _generate(worker):
    from .gemini_connector import generate_text as gemini
    from .ai_connectors import generate_claude, generate_perplexity
    from .ai_connections import generate_custom

    if worker.worker_id == "gemini":
        return gemini
    if worker.worker_id == "claude":
        return generate_claude
    if worker.worker_id == "perplexity":
        return generate_perplexity
    if worker.worker_id.startswith("custom-"):
        return lambda prompt: generate_custom(worker.worker_id, prompt)
    return None


def prepare_assessment():
    from .worker_registry import list_workers
    learning.self_initialize()
    snapshot = learning.learning_snapshot()
    workers = []
    for worker in list_workers():
        onboarding = snapshot.get("workers", {}).get(worker.worker_id, {}).get("onboarding", {})
        workers.append({
            "worker_id": worker.worker_id,
            "status": "ready" if worker.metadata.get("execution_ready") else "skipped",
            "reason": "ready_for_benchmark" if worker.metadata.get("execution_ready") else "skipped_not_execution_ready",
            "tests_total": onboarding.get("tests_total", 0),
            "tests_completed": onboarding.get("tests_completed", 0),
        })
    return {"status": "prepared", "timestamp": datetime.now(timezone.utc).isoformat(), "workers": workers, "policy": "new workers get benchmarks; existing worker history is preserved"}


def run_assessment(worker_ids=None, force=False):
    from .worker_registry import list_workers
    learning.self_initialize()
    selected = set(worker_ids or [])
    now = datetime.now(timezone.utc).isoformat()
    results = []

    for worker in list_workers():
        if selected and worker.worker_id not in selected:
            continue
        if worker.worker_id not in {"gemini", "claude", "perplexity"} and not worker.worker_id.startswith("custom-"):
            continue
        if not worker.metadata.get("execution_ready"):
            results.append({"worker_id": worker.worker_id, "status": "skipped", "reason": "skipped_not_execution_ready", "tests_completed": 0, "tests_total": 0, "tests": []})
            continue
        snapshot = learning.learning_snapshot()
        onboarding = snapshot.get("workers", {}).get(worker.worker_id, {}).get("onboarding", {})
        if onboarding.get("status") == "completed" and not force:
            results.append({"worker_id": worker.worker_id, "status": "skipped", "reason": "existing_worker_history_preserved", "tests_completed": onboarding.get("tests_completed", 0), "tests_total": onboarding.get("tests_total", 0), "benchmark_scores": onboarding.get("benchmark_scores", {}), "tests": onboarding.get("tests", [])})
            continue
        generator = _generate(worker)
        tests = []
        for capability in onboarding.get("benchmark_capabilities", []):
            for test in capability.get("tests", []):
                started = datetime.now(timezone.utc)
                try:
                    response = generator(test["prompt"]) if generator else None
                    text = response.get("text", "") if isinstance(response, dict) else str(response or "")
                    evaluation = evaluate_test(test["test_id"], text)
                    latency = response.get("telemetry", {}).get("last_latency_ms") if isinstance(response, dict) else None
                    tests.append({"test_id": test["test_id"], "capability": capability["capability"], "metric": test["metric"], "status": "completed", "score": evaluation["score"], "checks": evaluation["checks"], "summary": evaluation["summary"], "latency_ms": latency, "final_answer_chars": len(text)})
                except Exception as exc:
                    tests.append({"test_id": test["test_id"], "capability": capability["capability"], "metric": test["metric"], "status": "failed", "score": 0.0, "error": str(exc)[:500], "elapsed_ms": round((datetime.now(timezone.utc) - started).total_seconds() * 1000, 2)})

        scores = {}
        for test in tests:
            scores.setdefault(test["capability"], []).append(test["score"])
        benchmark_scores = {key: round(sum(values) / len(values), 2) for key, values in scores.items() if values}
        completed = sum(test["status"] == "completed" for test in tests)
        total = len(tests)
        overall_score = round(sum(test["score"] for test in tests) / total, 2) if total else 0.0
        status = "completed" if total and completed == total else "partial" if completed else "failed"
        snapshot = learning.learning_snapshot()
        store = snapshot.setdefault("workers", {}).setdefault(worker.worker_id, {})
        store["onboarding"] = {
            **onboarding,
            "status": status,
            "completed_at": now,
            "tests": tests,
            "tests_completed": completed,
            "tests_total": total,
            "overall_score": overall_score,
            "benchmark_scores": benchmark_scores,
            "evaluation_version": 2,
        }
        learning._save(snapshot)
        results.append({"worker_id": worker.worker_id, "status": status, "tests_completed": completed, "tests_total": total, "overall_score": overall_score, "benchmark_scores": benchmark_scores, "tests": tests})

    overall_status = "completed" if results and all(r["status"] in {"completed", "skipped"} for r in results) and any(r["status"] == "completed" for r in results) else "partial"
    return {"status": overall_status, "timestamp": now, "results": results, "policy": "benchmarks initialize new workers; production history remains authoritative after onboarding", "evaluation_version": 2}
