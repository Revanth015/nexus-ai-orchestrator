# NEXUS — Project Context & Stage Tracker

Read this file first in every new NEXUS development chat. Continue from the current stage; do not restart completed architecture work.

## Project
- Name: NEXUS — AI Corporate Manager / AI Orchestrator
- Repository: `Revanth015/nexus-ai-orchestrator`
- Local path: `D:\Projects\nexus-ai-orchestrator`
- Goal: free-first, execution-aware multi-AI orchestration. One business outcome enters NEXUS; Manager decomposes it, allocates AI employees, coordinates dependencies, executes work, performs QA/rework, learns from outcomes and makes final acceptance decisions.

## Non-negotiable requirements
- Free AI only; never silently use paid APIs/models.
- Never invent exact provider quota.
- Free-first and execution-aware routing.
- Immediate fallback for quota/rate-limit/auth/recoverable connector failures.
- Background execution OFF by default and explicitly controllable.
- New providers must be easy to add without changing orchestration core.
- Substantial outputs require independent QA and rework where needed.
- Never commit API keys/secrets.
- Development protocol: build → pull → run → test → fix → advance.

## Runtime
- Windows / Python 3.11.x / Node 24.x / npm 11.x
- Backend: FastAPI/Uvicorn at `http://127.0.0.1:8000/`
- Frontend: React/Vite at `http://localhost:5173/`
- Backend venv: `backend\.venv`
- CMD activation: `backend\.venv\Scripts\activate.bat`
- Use `npm.cmd` if PowerShell blocks `npm.ps1`.

## Completed stages

### Stage 1 — Base interface/backend
**PASSED** — React/Vite, FastAPI, health communication, system-ready/free-only/background-off states.

### Stage 2 — Prompt understanding
**PASSED** — deterministic intent analysis for research, files, data, writing, presentations, images, coding, current information, QA, deliverables, requirements and dependencies.

### Stage 3 — Workflow graph
**PASSED** — task IDs/types/dependencies/inputs/outputs/status/quality gates; dependency graph rather than flat tasks.

### Stage 4 — Worker registry + routing
**PASSED** — built-in workers, preferred-vs-current execution distinction, execution-aware routing, dynamic task performance learning, score caps.

### Stage 5 — Provider connectors
**IMPLEMENTED** — Gemini, Perplexity, Claude and OpenAI-compatible custom connector path, telemetry, failure classification and explicit execution.

### Stage 6 — Custom AI employee management
**FUNCTIONAL**
- Add AI UI exists.
- Name/provider/API key/model/base URL/free verification/capabilities can be registered.
- Credentials are hidden from public worker responses.
- Delete works.
- Connection records persist locally.
- Custom workers are execution-ready only after a successful connection test.
- Proper update/edit endpoint is still a future lifecycle-hardening item.

### Stage 7 — Groq real connection
**PASSED**
Confirmed externally and through NEXUS:
- Provider: `groq`
- Base URL: `https://api.groq.com/openai/v1`
- Model: `openai/gpt-oss-120b`
- Endpoint: PASS
- Authentication: PASS
- Model: PASS
- Completion: PASS
- Overall: PASS

The Groq playground URL is not the API base URL.

### Stage 8 — Diagnostics / React-safe errors
**PASSED ENOUGH TO CONTINUE**
Diagnostics expose endpoint/auth/model/completion/latency/overall and structured provider errors. Earlier React crashes from rendering `{message, code, http_status}` objects were corrected.

### Stage 9 — Custom AI execution
**PARTIALLY VALIDATED**
Custom Groq has participated in a real NEXUS mission and produced worker outputs. Remaining validation is full task completion, artifact chaining and final manager/QA acceptance.

## Current stage

### Stage 10 — Self-assessment v2
**BACKEND IMPLEMENTED — LOCAL TEST REQUIRED; FRONTEND PRESENTATION STILL NEEDS A SMALL PATCH**

Original self-assessment produced brittle partial results such as Groq `6/11` because several checks depended on exact word counts/formatting/keywords.

Stage 10 v2 has now been added to GitHub:
- `backend/app/self_assessment_v2.py` — robust objective-but-tolerant evaluator.
- `backend/app/main.py` — `/workers/self-initialize` and `/workers/self-initialize/run` are wired to v2.
- `backend/app/worker_registry.py` — benchmark scores are overlaid onto custom worker capability profiles as initial evidence.

### Self-assessment v2 behavior
- Uses final response text rather than treating reasoning traces as the final answer.
- Scores individual checks and produces a 0–100 score per benchmark.
- Produces capability-level benchmark scores.
- Stores benchmark results in worker onboarding data.
- Distinguishes `completed`, `partial`, `failed` and `skipped` backend states.
- Skips workers that are not execution-ready.
- Preserves existing worker production history.
- A benchmark failure does not automatically make a successfully connected worker offline.
- Detailed failed checks/reasons are returned in the API result.

### Remaining Stage 10 UI item
`frontend/src/ManagerDashboard.jsx` still contains the earlier assessment display logic where `assessmentMode === "results"` can make the banner read `Assessment completed` even when the backend worker status is `partial`. The next frontend patch must display the actual backend state and expose capability scores/individual failed checks cleanly.

## Stage 11 — Real task execution + manager acceptance
**NEXT AFTER STAGE 10 UI TEST**
A real mission already reached custom Groq and generated worker outputs, but one decomposed task was incomplete and the manager decision was REJECT. The next goal is to determine whether the remaining issue is task routing, execution capability, dependency/artifact handling or QA acceptance.

## Stage 12 — Artifact chaining
**NOT COMPLETE**
Worker outputs must become explicit downstream inputs and dependencies must be enforced during execution.

## Stage 13 — Independent QA + rework
**NOT COMPLETE**
Producer-independent QA, exact rework problem recording, maximum three reworks, and Manager final acceptance.

## Stage 14 — Multi-worker optimization
**NOT COMPLETE**
Compare worker combinations using task fit, quality, free availability, reliability, latency, failure history, dependency compatibility and output format compatibility.

## Stage 15 — Background execution
**NOT COMPLETE**
Must remain OFF by default and explicitly controllable.

## Current product status
```text
Core UI/backend                  PASS
Prompt analysis                 PASS
Workflow/decomposition          PASS
Worker registry/routing         PASS
Provider framework              PASS
Custom AI add                   PASS
Custom AI connection test       PASS
Groq real API validation        PASS
Groq NEXUS execution            PARTIALLY VALIDATED
Self-assessment v2 backend      IMPLEMENTED / NEEDS LOCAL TEST
Self-assessment v2 UI           NEXT SMALL PATCH
Artifact chaining               PENDING
Independent QA/rework           PENDING
Multi-worker optimization       PENDING
Background execution            PENDING
```

## Important recent commits
- `fix: validate compatible AI with real chat completion`
- `fix: make diagnostics UI-safe and match provider request headers`
- `fix: robustly parse compatible AI completion responses`
- `fix: make diagnosis fields React-safe primitives`
- `feat: add robust self-assessment v2 engine`
- `feat: wire self-assessment v2 into onboarding endpoints`
- `feat: feed onboarding benchmark scores into worker profiles`

## Handoff
Current continuation point:
**Stage 10 — run the new self-assessment v2 locally, inspect the JSON/result, then patch the assessment UI to accurately display completed/partial/failed/skipped and benchmark scores. After that continue Stage 11 real mission completion.**

Never fake connection, capability, quota or execution status. Move quickly, but test each stage before declaring it passed.
