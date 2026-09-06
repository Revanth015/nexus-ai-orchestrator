# NEXUS — Project Context & Stage Tracker

Read this file first in every new NEXUS development chat. Continue from the current implementation; do not restart completed architecture work.

## Project
- Name: NEXUS — AI Corporate Manager / AI Orchestrator
- Repository: `Revanth015/nexus-ai-orchestrator`
- Local path: `D:\Projects\nexus-ai-orchestrator`
- Active development branch: `workspace-foundation`
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
- Unconnected custom AIs must not be executable or selectable as direct workers.
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
IMPLEMENTED: self-assessment v2 with tolerant objective checks, 0–100 benchmark scores, capability priors, production-history preservation, final-answer preference over reasoning traces, detailed failed checks and completed/partial/failed/skipped states. The UI displays backend assessment state rather than inferring completion from a UI mode.

## Workspace foundation
Implemented on `workspace-foundation` as the current product layer:
- Persistent workspace model and workspace-scoped objectives/tasks/runs/artifacts/activity.
- Workspace switcher and workspace-aware mission/task/run flows.
- Artifact browsing and activity/dashboard views.
- Seeded default workspace and legacy compatibility.
- Custom AI lifecycle remains available inside the workspace.
- Current UI is a clean NEXUS AI Workspace with New Chat, AI workforce, Auto routing, AI connections, file attachment and chat execution.
- Built-in initial workers are NEXUS Local Tools, Gemini and NEXUS Local Validator. Perplexity and Claude are not shown as initial built-ins but remain architecturally supported/custom-connectable.

## Smart Auto routing v2
Implemented:
- Deterministic prompt classification selects task type in Auto mode.
- Uploaded files force `file_analysis` routing.
- Task types map to capability requirements.
- Router filters by execution readiness, eligibility, free-only policy and concrete executor support.
- Ranking combines capability fit, task-specific performance evidence, reliability, efficiency, execution readiness and exploration.
- Shared selection key is used for Auto/Manager ranking work.
- Direct worker selection remains available for connected workers only.

Important current implementation note:
- Manager selection was updated to use the Smart Auto ranking key rather than its older task-performance-only ranking path.
- This alignment has not yet been fully validated through the user's complete local mission end-to-end test; that remains a future validation item.

## Core hardening completed
The post-MVP engineering audit identified runtime-enforcement gaps. The following fixes are now in the repository:

### Executor-aware routing
`worker_router.py` checks concrete runtime executor support in addition to capability/readiness/free status. Local tools are eligible for file/data analysis; the local validator is eligible for QA; text AI/custom workers are eligible for supported text tasks. Image generation is not falsely advertised as executable.

### Automatic failover
`execution.py` retries through safe executable candidates after worker failure, records failed worker IDs and exposes attempt/fallback telemetry. Manager-directed allocations can fail over safely instead of terminating immediately.

### Response quality gate
`response_quality.py` provides a conservative deterministic post-execution gate for empty/very-short outputs, obvious execution errors and placeholder-only responses. It is not a factuality judge. If a normal `/execute` response fails this gate and fallback is allowed, NEXUS excludes the failed worker and routes to another execution-ready worker.

### Manager verification / QA
Mission execution uses the planned independent `quality_review` gate as the verification mechanism when a mission already contains a QA task, avoiding duplicate verification calls. QA requests structured JSON but retains legacy text parsing compatibility.

### Rework
A QA REWORK creates a new rework task and a new independent QA task. The exact QA problem is carried into the rework prompt. Rework cycles are capped at three.

### Artifact hand-offs
Artifacts carry task/source IDs, type, version and content. Downstream tasks consume declared upstream artifact names only after dependencies complete.

### Resource accounting
Execution reports actual calls consumed, including fallback attempts and collaborators. Mission memory stores the actual execution resource count rather than recomputing Manager estimates.

### Learning
Worker learning uses re-entrant locking, atomic local writes, observation-based confidence and a 30-day recency factor. Collaboration outcomes can be recorded and queried.

### Custom AI lifecycle
Custom workers support ADD, TEST/DIAGNOSE, UPDATE, ENABLE/DISABLE and DELETE. Any configuration update invalidates the previous successful test. API keys are never returned by public worker responses.

### Connection/readiness enforcement
Custom workers are considered execution-ready only when enabled, an API key is configured and the connection test has succeeded. Unconnected custom AIs are visible in the UI but disabled for direct selection/execution.

The workspace initially exposed readiness inconsistently: the registry stored runtime connection state inside worker metadata while the frontend expected top-level worker fields. This was fixed at the `/workers` API boundary by explicitly exposing `connected`, `execution_ready`, `api_key_configured`, `test_status`, `model`, `base_url` and `free_verified`.

### File safety
Uploads validate file IDs, keep server storage paths private, preserve original filenames using local metadata, and explicitly expose extraction truncation limits/metadata.

### Local state durability
Mission memory, audit log, worker learning and custom connection JSON stores use atomic replacement. JSON remains intentionally local-install storage; SQLite is the next scale migration when multi-process/concurrent mission persistence becomes necessary.

### Testing / CI
- Added `pytest`.
- Added backend regression tests for executor-aware routing, free-only filtering and failover.
- Fixed the smoke test's invalid Manager decision request.
- Added GitHub Actions CI for backend compile/tests/import and frontend build.
- The hardening baseline CI workflow previously completed successfully.
- Do not treat GitHub commit existence as proof of local runtime testing.

## Recently checked locally by the user
### Groq connection
Verified real Groq configuration:
- Provider: `groq`
- Base URL: `https://api.groq.com/openai/v1`
- Model: `openai/gpt-oss-120b`
- NEXUS diagnostic result: Endpoint PASS / Authentication PASS / Model PASS / Completion PASS / Overall PASS.

After the connection-state API fix, the user pulled/restarted the workspace and confirmed that the Groq connection state now displays correctly and is usable. This confirms the specific UI/API readiness-state bug is fixed in the user's local environment.

### Custom connection UI state
The user also confirmed the current connection panel can show successful diagnostic details for Groq and unconnected custom workers remain unconfigured/disabled rather than being falsely selectable.

### Not yet locally verified
- Full hardened mission path with the user's real connected worker(s), including Manager allocation → execution → failover → artifact hand-off → independent QA → rework → second QA → final Manager acceptance → learning/audit/memory.
- Full local regression suite after the most recent commits.
- Full local validation of Manager/Smart Auto ranking equivalence.

## Current implementation limitations
These are deliberate remaining scale/product items, not hidden capabilities:
- JSON persistence is still single-install local storage, although writes are atomic.
- Background execution is not implemented and remains OFF by default.
- Current remote/custom workers are text-chat executors; native image generation/vision execution is not implemented.
- File extraction is bounded for predictable resource use and reports truncation.
- Multi-worker optimization is currently evidence-aware collaboration/routing, not a full historical combination optimizer.
- Adaptive replanning has the state model and execution signals but should be further integrated into a durable mission scheduler for true dynamic replanning.
- Gemini is a built-in connector path and has not been treated as a Custom AI connection for the connection-panel test flow.

## Next engineering target
Do not start it automatically in the next chat unless requested. The next target is:

1. Fully locally validate the Manager + Smart Auto ranking alignment.
2. Then validate the complete hardened mission pipeline with the user's real connected worker(s).
3. Fix any observed runtime issues before adding another major product feature.

Target validation path:

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

## Key files
- `backend/app/main.py` — API surface and worker API readiness projection
- `backend/app/execution.py` — mission/task execution, failover, QA/rework and Manager allocation
- `backend/app/worker_router.py` — executor-aware dynamic routing and Smart Auto ranking
- `backend/app/worker_registry.py` — worker profiles/readiness
- `backend/app/worker_learning.py` — evidence/learning
- `backend/app/manager_decision.py` — Manager decision policy
- `backend/app/self_assessment_v2.py` — onboarding benchmark engine
- `backend/app/ai_connections.py` — custom AI lifecycle
- `backend/app/file_store.py` — upload/extraction safety
- `backend/app/mission_execution_service.py` — mission persistence/audit integration
- `backend/app/mission_memory.py` — mission state/memory
- `backend/app/audit_log.py` — audit events
- `backend/app/response_quality.py` — deterministic response quality gate
- `frontend/src/NexusWorkspace.jsx` — current workspace UI and connection state/selection behavior
- `frontend/src/workspace.css` — workspace styling
- `backend/tests/test_core_hardening.py` — regression tests
- `.github/workflows/ci.yml` — CI gate
- `docs/ENGINEERING_HARDENING.md` — engineering hardening baseline

## Handoff
Current stage: **Workspace foundation + core hardening implemented; Groq connection-state bug fixed and locally confirmed; full hardened end-to-end validation and Manager/Auto ranking validation remain.**

Do not restart the architecture. Continue from `workspace-foundation`. Preserve the build → pull → run → test → fix → advance protocol. Do not claim local test results unless the user has actually run them or a verifiable CI run supports the claim.

## Important verified Groq configuration
- Provider: `groq`
- Base URL: `https://api.groq.com/openai/v1`
- Model: `openai/gpt-oss-120b`
- Previous NEXUS diagnostic: Endpoint PASS / Authentication PASS / Model PASS / Completion PASS / Overall PASS.
- Current user-confirmed state: Groq now appears connected/usable in the NEXUS workspace after the readiness-field fix.
- Never claim exact remaining Groq quota unless the provider exposes it at runtime.
