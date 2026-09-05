# NEXUS — Project Context & Stage Tracker

Read this file first in every new NEXUS development chat. Continue from the current implementation; do not restart completed architecture work.

## Project
- Name: NEXUS — AI Corporate Manager / AI Orchestrator
- Repository: `Revanth015/nexus-ai-orchestrator`
- Local path: `D:\Projects\nexus-ai-orchestrator`
- Goal: free-first, execution-aware multi-AI orchestration. The user is CEO; NEXUS is Manager; connected AI/tool workers are employees. The Manager understands an outcome, decomposes it, allocates executable workers, coordinates hand-offs, executes, independently reviews, reworks and makes final acceptance decisions.

## Non-negotiable rules
- Never silently incur a paid AI/API charge.
- Never invent exact provider quota.
- Unknown/free-unverified providers are not selected in Free-Only mode.
- Connector failures must trigger safe fallback when another executable worker exists.
- Background execution is OFF by default.
- New providers must remain isolated behind the worker/provider interface.
- Substantial outputs require independent QA.
- QA recommends PASS/REWORK; the Manager owns final acceptance.
- Maximum three rework cycles.
- Never commit API keys or local runtime state.
- Development protocol: build → pull → run → test → fix → advance.

## Runtime
- Windows
- Python 3.11.x
- Node 24.x / npm 11.x
- Backend: FastAPI/Uvicorn at `http://127.0.0.1:8000/`
- Frontend: React/Vite at `http://localhost:5173/`
- Backend virtual environment: `backend\.venv`
- PowerShell may require `npm.cmd` instead of `npm`.

## Completed foundation
### Stages 1–4
PASSED: base UI/backend, deterministic prompt analysis, workflow graph/dependencies, worker registry and dynamic task-specific routing.

### Stage 5
IMPLEMENTED: Gemini, Claude, Perplexity and OpenAI-compatible custom connector paths with telemetry/error handling.

### Stage 6–9
PASSED/PARTIALLY VALIDATED: custom AI employee add/test/diagnose/delete, Groq real API validation, React-safe diagnostics, and custom AI participation in real missions.

### Stage 10
IMPLEMENTED: self-assessment v2 with tolerant objective checks, 0–100 benchmark scores, capability priors, production-history preservation, final-answer preference over reasoning traces, detailed failed checks and completed/partial/failed/skipped states. The UI now displays the backend assessment state rather than inferring completion from a UI mode.

## Core hardening completed
The post-MVP engineering audit identified runtime-enforcement gaps. The following fixes are now in the repository:

### Executor-aware routing
`worker_router.py` now checks concrete runtime executor support in addition to capability/readiness/free status. Local tools are eligible for file/data analysis; the local validator is eligible for QA; text AI/custom workers are eligible for supported text tasks. Image generation is not falsely advertised as executable.

### Automatic failover
`execution.py` now retries through safe executable candidates after worker failure, records failed worker IDs and exposes attempt/fallback telemetry. Manager-directed allocations can fail over safely instead of terminating immediately.

### Manager verification / QA
Mission execution uses the planned independent `quality_review` gate as the verification mechanism when a mission already contains a QA task, avoiding duplicate verification calls. QA requests structured JSON but retains legacy text parsing compatibility.

### Rework
A QA REWORK creates a new rework task and a new independent QA task. The exact QA problem is carried into the rework prompt. Rework cycles are capped at three.

### Artifact hand-offs
Artifacts now carry task/source IDs, type, version and content. Downstream tasks consume declared upstream artifact names only after dependencies complete.

### Resource accounting
Execution reports actual calls consumed, including fallback attempts and collaborators. Mission memory now stores the actual execution resource count rather than recomputing Manager estimates.

### Learning
Worker learning now uses re-entrant locking, atomic local writes, observation-based confidence and a 30-day recency factor. Collaboration outcomes can be recorded and queried.

### Custom AI lifecycle
Custom workers support ADD, TEST/DIAGNOSE, UPDATE, ENABLE/DISABLE and DELETE. Any configuration update invalidates the previous successful test. API keys are never returned by public worker responses.

### File safety
Uploads validate file IDs, keep server storage paths private, preserve original filenames using local metadata, and explicitly expose extraction truncation limits/metadata.

### Local state durability
Mission memory, audit log, worker learning and custom connection JSON stores now use atomic replacement. JSON remains intentionally local-install storage; SQLite is the next scale migration when multi-process/concurrent mission persistence becomes necessary.

### Testing / CI
- Added `pytest`.
- Added backend regression tests for executor-aware routing, free-only filtering and failover.
- Fixed the smoke test's invalid Manager decision request.
- Added GitHub Actions CI for backend compile/tests/import and frontend build.
- CI run for the final hardening baseline completed successfully on the latest hardening workflow commit.

## Current implementation limitations
These are deliberate remaining scale/product items, not hidden capabilities:
- JSON persistence is still single-install local storage, although writes are atomic.
- Background execution is not implemented and remains OFF by default.
- Current remote/custom workers are text-chat executors; native image generation/vision execution is not implemented.
- File extraction is bounded for predictable resource use and reports truncation.
- Multi-worker optimization is currently evidence-aware collaboration/routing, not a full historical combination optimizer.
- Adaptive replanning has the state model and execution signals but should be further integrated into a durable mission scheduler for true dynamic replanning.

## Next engineering target
Before adding major features, perform a real local end-to-end validation of the hardened pipeline:

```text
CEO objective
 → Manager analysis
 → dependency graph
 → executor-aware allocation
 → worker execution
 → automatic failover if needed
 → artifact hand-off
 → independent QA
 → targeted rework (≤3)
 → independent QA again
 → Manager ACCEPT/REJECT
 → actual resource accounting
 → learning/audit/memory
```

Then proceed to the next product layer only after this path passes locally with the user's real connected workers.

## Important verified Groq configuration
- Provider: `groq`
- Base URL: `https://api.groq.com/openai/v1`
- Model: `openai/gpt-oss-120b`
- Previous NEXUS diagnostic: Endpoint PASS / Authentication PASS / Model PASS / Completion PASS / Overall PASS.
- Never claim exact remaining Groq quota unless the provider exposes it at runtime.

## Key files
- `backend/app/main.py` — API surface
- `backend/app/execution.py` — mission/task execution, failover, QA/rework
- `backend/app/worker_router.py` — executor-aware dynamic routing
- `backend/app/worker_registry.py` — worker profiles/readiness
- `backend/app/worker_learning.py` — evidence/learning
- `backend/app/manager_decision.py` — Manager decision policy
- `backend/app/self_assessment_v2.py` — onboarding benchmark engine
- `backend/app/ai_connections.py` — custom AI lifecycle
- `backend/app/file_store.py` — upload/extraction safety
- `backend/app/mission_execution_service.py` — mission persistence/audit integration
- `backend/app/mission_memory.py` — mission state/memory
- `backend/app/audit_log.py` — audit events
- `frontend/src/ManagerDashboard.jsx` — Manager UI
- `backend/tests/test_core_hardening.py` — regression tests
- `.github/workflows/ci.yml` — CI gate
- `docs/ENGINEERING_HARDENING.md` — engineering hardening baseline

## Handoff
Current stage: **Core Hardening completed; local end-to-end validation is next.**

Do not restart the architecture. Pull the latest `main`, run backend/frontend, execute the regression suite, then test a real mission with the user's connected worker(s). Fix observed runtime issues before adding another major feature.
