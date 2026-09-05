from __future__ import annotations

from app import execution
from app.models import CapabilityScores, FreeStatus, ResourceState, WorkerProfile, WorkerType
from app.worker_router import route_task


def worker(worker_id: str, *, free: FreeStatus = FreeStatus.VERIFIED_FREE, ready: bool = True, tasks=None, reasoning=80):
    return WorkerProfile(
        worker_id=worker_id,
        name=worker_id,
        provider="test",
        worker_type=WorkerType.AI,
        capabilities=CapabilityScores(reasoning=reasoning, research=reasoning, documents=reasoning, reliability=90, efficiency=90),
        resource=ResourceState(free_status=free, confidence=100 if free != FreeStatus.UNKNOWN else 0),
        metadata={"execution_ready": ready, "custom": worker_id.startswith("custom-"), "executor_tasks": tasks or ["general_reasoning", "research", "writing", "quality_review"]},
    )


def test_router_rejects_worker_without_runtime_executor(monkeypatch):
    monkeypatch.setattr("app.worker_router.list_workers", lambda: [worker("local-tools", tasks=["data_analysis", "file_analysis"]), worker("custom-a")])
    result = route_task("research", free_only=True)
    assert result.recommended_worker_id == "custom-a"
    local = next(c for c in result.candidates if c.worker_id == "local-tools")
    assert local.eligible_for_task is False


def test_router_does_not_treat_unknown_worker_as_free(monkeypatch):
    monkeypatch.setattr("app.worker_router.list_workers", lambda: [worker("custom-unknown", free=FreeStatus.UNKNOWN)])
    result = route_task("general_reasoning", free_only=True)
    assert result.recommended_worker_id is None
    assert result.execution_ready is False


def test_execute_task_fails_over_to_next_safe_worker(monkeypatch):
    candidates = [worker("primary"), worker("fallback")]

    def fake_route(task_type, *, free_only=True, exclude_worker_ids=None):
        excluded = exclude_worker_ids or set()
        from app.worker_router import WorkerCandidate, WorkerRouteResponse
        visible = [w for w in candidates if w.worker_id not in excluded]
        cs = [WorkerCandidate(worker_id=w.worker_id, name=w.name, score=90 - i * 10, capability_score=80, task_performance_score=80, confidence=50, execution_ready=True, resource_status="verified_free", eligible=True, eligible_for_task=True, exploration=False, reason="test") for i, w in enumerate(visible)]
        return WorkerRouteResponse(task_type=task_type, capability="reasoning", recommended_worker_id=cs[0].worker_id if cs else None, execution_ready=bool(cs), candidates=cs, fallback_worker_id=cs[1].worker_id if len(cs) > 1 else None)

    calls = []
    monkeypatch.setattr(execution, "route_task", fake_route)
    monkeypatch.setattr(execution, "read_file", lambda file_id: {"file_id": file_id, "filename": "x.txt", "extension": ".txt", "content": "x"})
    monkeypatch.setattr(execution, "record_result", lambda *args, **kwargs: None)

    def fake_run(worker_id, task_type, prompt, files):
        calls.append(worker_id)
        if worker_id == "primary":
            raise RuntimeError("simulated provider failure")
        return {"text": "fallback result", "telemetry": {"last_latency_ms": 5}}

    monkeypatch.setattr(execution, "_run_worker", fake_run)
    result = execution.execute_task(execution.ExecutionRequest(task_type="general_reasoning", prompt="test"), free_only=True)
    assert result.worker_id == "fallback"
    assert result.fallback_used is True
    assert result.failed_worker_ids == ["primary"]
    assert calls == ["primary", "fallback"]


def test_execute_task_can_disable_fallback(monkeypatch):
    from app.worker_router import WorkerCandidate, WorkerRouteResponse
    candidate = WorkerCandidate(worker_id="primary", name="primary", score=90, capability_score=80, task_performance_score=80, confidence=50, execution_ready=True, resource_status="verified_free", eligible=True, eligible_for_task=True, exploration=False, reason="test")
    monkeypatch.setattr(execution, "route_task", lambda *args, **kwargs: WorkerRouteResponse(task_type="general_reasoning", capability="reasoning", recommended_worker_id="primary", execution_ready=True, candidates=[candidate]))
    monkeypatch.setattr(execution, "record_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(execution, "_run_worker", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("failure")))
    try:
        execution.execute_task(execution.ExecutionRequest(task_type="general_reasoning", prompt="test", allow_fallback=False), free_only=True)
    except RuntimeError as exc:
        assert "failure" in str(exc)
    else:
        raise AssertionError("Expected provider failure")
