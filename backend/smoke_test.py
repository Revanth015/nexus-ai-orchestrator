"""Local smoke test for the NEXUS Manager -> AI employee workflow.

Run from backend with the API already running:
    python smoke_test.py
"""
from __future__ import annotations
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"

def request(method: str, path: str, payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try: data = json.loads(exc.read().decode())
        except json.JSONDecodeError: data = {"detail": str(exc)}
        return exc.code, data

def check(name: str, status: int, data: dict):
    ok = 200 <= status < 300
    print(f"{'PASS' if ok else 'FAIL'}  {name} [{status}]")
    if not ok: print(json.dumps(data, indent=2))
    return ok

def main() -> int:
    checks = []
    status, data = request("GET", "/health"); checks.append(check("health", status, data))
    status, data = request("GET", "/workers"); checks.append(check("worker registry", status, data))
    status, data = request("GET", "/route/general_reasoning"); checks.append(check("task routing", status, data))
    status, data = request("POST", "/manager/decide/general_reasoning", {"prompt": "Choose an executable worker for a short business reasoning task."})
    checks.append(check("manager allocation", status, data))
    if status == 200: print("  selected worker:", data.get("selected_worker_id")); print("  manager action:", data.get("action"))
    status, data = request("POST", "/execute", {"task_type": "general_reasoning", "prompt": "Reply in one short sentence: why should a manager allocate work based on employee performance?"})
    checks.append(check("single employee execution", status, data))
    if status == 200: print("  executed by:", data.get("worker_id"), "attempts:", data.get("attempts"))
    status, data = request("POST", "/execute-mission", {"prompt": "Explain in exactly three short sentences why NEXUS should use a free-first worker routing policy."})
    checks.append(check("manager mission execution", status, data))
    if status == 200:
        print("  mission status:", data.get("status")); print("  manager decision:", data.get("manager_decision")); print("  tasks:", len(data.get("tasks", []))); print("  resources:", data.get("resource_used"), "/", data.get("resource_budget")); print("  reworks:", data.get("rework_count"), "/", data.get("max_reworks"))
    passed = sum(checks); print(f"\n{passed}/{len(checks)} smoke checks passed.")
    return 0 if all(checks) else 1

if __name__ == "__main__": raise SystemExit(main())
