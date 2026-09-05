# NEXUS — Project Context & Stage Tracker

> Read this file first in every new NEXUS development chat. Continue from the current stage; do not restart the architecture discussion.

## Project
- Name: NEXUS — AI Corporate Manager / AI Orchestrator
- Repository: `Revanth015/nexus-ai-orchestrator`
- Local path: `D:\Projects\nexus-ai-orchestrator`
- Goal: corporate-ready, free-first multi-AI orchestration. User gives one business outcome; NEXUS understands it, decomposes it, selects suitable AI employees by task-specific evidence, coordinates dependencies, executes work, quality-checks outputs, reworks when needed, records learning and makes the final acceptance decision.

## Non-negotiable requirements
1. Free AI only; never silently use paid APIs/models.
2. Never invent exact remaining quota.
3. If quota is not exposed, mark it unknown and estimate only from observed telemetry, rate-limit/quota errors and reset information when observable.
4. Immediate fallback on quota, rate-limit, authentication, temporary or recoverable connector failures.
5. Free-first, execution-aware routing.
6. Background execution must be controllable and default OFF.
7. Adding a new AI/provider should be easy and isolated from the orchestration core.
8. Quality checks must be applied to substantial outputs; rework until satisfactory or only non-material issues remain.
9. NEXUS should compare/mix multiple worker combinations for difficult tasks.
10. Never commit API keys/secrets.
11. Build in stages: build → pull → run → test → fix → only then advance.

## Runtime
- Windows
- Python 3.11.x
- Node 24.x
- npm 11.x; use `npm.cmd` if PowerShell blocks `npm.ps1`
- Backend: FastAPI/Uvicorn
- Frontend: React/Vite
- Frontend: `http://localhost:5173/`
- Backend: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`
- Backend venv: `backend\.venv`
- CMD activation: `backend\.venv\Scripts\activate.bat`

## Stages

### Stage 1 — Base interface/backend
**PASSED**
- React/Vite UI works.
- FastAPI works.
- Frontend/backend health communication works.
- System-ready, free-only and background-off states work.

### Stage 2 — Prompt understanding
**PASSED**
- Local deterministic analyzer; no external AI required.
- Detects research, file analysis, data analysis, writing, presentation, image generation, coding, current information and quality review.
- Detects semantic visual terms.
- Detects deliverables, requirements and dependencies.
- Confidence is heuristic and must not be presented as true model confidence.

### Stage 3 — Task decomposition/workflow graph
**PASSED**
- Creates task IDs, types, titles, dependencies, inputs, outputs, status and quality gates.
- Dependency graph rather than flat task list.

Validated pattern:
```text
Research → research_brief
File analysis → file_analysis
Data analysis ← research_brief + file_analysis → analysis_findings
Presentation ← previous artifacts → presentation_draft
Quality review ← outputs → PASS/REWORK
```

### Stage 4 — Worker registry + capability routing
**PASSED**
Conceptual built-in workers:
- Perplexity — research
- Gemini — general/multimodal/presentation
- Claude — reasoning/coding/documents
- NEXUS Local Tools
- NEXUS Local Validator

Routing distinguishes preferred capability profile from current executable availability. Unconnected workers are not executable. Scores are capped at 100. Learning can modify task-specific performance over time.

### Stage 5 — Real provider connectors
**PASSED for implementation; local provider validation is incremental**

Implemented:
- Gemini connector and telemetry.
- Perplexity connector.
- Claude connector.
- OpenAI-compatible custom AI connector path.
- Explicit local `.env` loading where required.
- Failure classification and execution readiness.

Provider rules:
- No automatic paid-model selection.
- Connector calls happen explicitly when a test/execution requires them.
- Exact provider quota is never fabricated.

### Stage 6 — Custom AI employee management
**BUILT / FUNCTIONAL — needs final lifecycle hardening**

The NEXUS UI now has **Add AI** in the workforce panel. A user can register a new AI employee with:
- Name
- Provider
- API key
- Model name
- Base URL
- Free verification flag
- Optional capability scores

Current custom AI flow:
```text
Add AI
  ↓
Persist local connection record
  ↓
Worker appears in workforce
  ↓
Initially not execution-ready
  ↓
Test connection
  ↓
Successful completion test
  ↓
execution_ready = true
  ↓
Worker becomes eligible for routing
```

Credentials are not returned by the public worker list. Local connection records remain outside Git and API keys must never be committed.

Current backend endpoints:
```text
GET    /workers/connections
POST   /workers/connections
DELETE /workers/connections/{worker_id}
POST   /workers/connections/{worker_id}/test
POST   /workers/connections/{worker_id}/diagnose
GET    /workers
```

**Known remaining lifecycle item:** add a proper update/edit endpoint and ensure changing credentials/model/base URL invalidates the previous successful test until the new configuration passes again.

### Stage 7 — Real custom AI connection validation
**PASSED for Groq / OpenAI-compatible path**

Groq was tested outside NEXUS first using the real API:
```text
GET https://api.groq.com/openai/v1/models
POST https://api.groq.com/openai/v1/chat/completions
```

The user's direct test successfully returned:
```text
GROQ TEST PASSED
```

NEXUS was then corrected so the Groq custom employee could successfully report:
```text
Endpoint         PASS
Authentication  PASS
Model           PASS
Completion      PASS
Overall         PASS
```

The confirmed working Groq configuration used:
```text
Provider: groq
Base URL: https://api.groq.com/openai/v1
Model: openai/gpt-oss-120b
```

Important lesson: the Groq playground URL is not the API base URL. The API base URL is the OpenAI-compatible API endpoint above.

The earlier HTTP 403 / error code 1010 issue was investigated externally and was not caused by the model name or base URL once the direct curl completion test succeeded. NEXUS's request path/headers and completion handling were subsequently corrected.

### Stage 8 — Diagnostics + React-safe error handling
**IMPLEMENTED / VERIFIED ENOUGH TO CONTINUE**

Diagnostics now expose separate stages:
```text
Endpoint
Authentication
Model
Completion
Latency
Overall
```

Provider errors are represented as structured data, but the frontend must never render an object directly as a React child. Earlier errors such as:
```text
Objects are not valid as a React child
```
were caused by structured `{message, code, http_status}` objects being rendered directly. The diagnostic UI/backend path was updated to use React-safe primitives/strings.

The latest successful Groq diagnostic demonstrates that authentication and completion are genuinely working, not merely that the endpoint exists.

### Stage 9 — Custom AI execution path
**WORKING / END-TO-END EXECUTION PARTIALLY VALIDATED**

The worker registry converts stored custom connections into `WorkerProfile` records. A custom worker is execution-ready only when:
```text
enabled == true
AND api_key_configured == true
AND test_status == "ok"
```

The execution layer recognizes `custom-*` workers and routes execution through the custom provider completion function.

The user has run a real NEXUS mission containing a custom Groq worker. The dashboard showed Groq as READY and the mission generated worker outputs. Therefore the custom AI is no longer only a connection-test feature; it is participating in the orchestration pipeline.

Current remaining validation is to prove that all decomposed tasks can be executed successfully and that final manager acceptance/QA completes.

### Stage 10 — Worker self-assessment / onboarding
**CURRENT STAGE — PARTIAL; THIS IS THE NEXT PATCH TARGET**

Self-assessment was implemented with task-specific benchmark suites for:
- reasoning
- research
- data analysis
- documents
- coding
- presentation
- vision readiness

Policy:
```text
New worker → benchmark prior capability
Existing worker → preserve historical production evidence
```

The UI currently shows benchmark status per worker, including observations and test counts.

Observed current Groq result:
```text
Groq
ASSESSED
partial
Tests: 6/11
```

Other unconnected workers correctly show:
```text
SKIPPED
skipped_not_execution_ready
```

### Known Stage 10 issue
The benchmark engine currently uses brittle deterministic checks for some tests (exact word counts, exact formatting, required keywords, etc.). This can mark a capable reasoning model as `partial` even when the underlying answer is correct.

There is also a model-output handling concern: OpenAI-compatible reasoning models may return a separate `reasoning` field. Benchmark evaluation must prefer actual final answer content and must not evaluate reasoning traces as the final answer when `content` is present/available.

The self-assessment banner currently says `Assessment completed` even when an individual worker is `partial`; this must be corrected to clearly distinguish:
```text
COMPLETED
PARTIAL
FAILED
SKIPPED
```

### Stage 10 next patch
Implement **Self-Assessment v2**:
1. Robustly separate final answer from reasoning for OpenAI-compatible responses.
2. Make benchmark evaluation less brittle while retaining objective checks.
3. Score each capability on a 0–100 scale instead of only binary pass/fail.
4. Store benchmark capability scores against the worker onboarding record.
5. Feed benchmark scores into execution-aware task routing as initial evidence/prior.
6. Preserve existing workers' historical production evidence as authoritative after onboarding.
7. Show individual benchmark results, failed checks and reasons in the UI.
8. Clearly display partial/failed/skipped state.
9. Do not benchmark workers that are not execution-ready.
10. Do not let benchmark failures silently make a successfully connected worker appear offline.

### Stage 11 — Real task execution + manager acceptance
**IN PROGRESS AFTER STAGE 10**

A real mission has been executed through NEXUS with the custom Groq worker. The mission reached worker outputs, but one decomposed task was not completed and the manager decision was REJECT.

This means the broad pipeline is alive:
```text
User prompt
 → Manager
 → decomposition
 → worker allocation
 → custom AI execution
 → worker outputs
 → manager/QA
```

The remaining issue is task-level execution/routing/QA completion, not basic Groq connectivity.

### Stage 12 — Artifact chaining
**NOT YET COMPLETE**
- Worker output must become explicit downstream task input.
- Dependencies must be enforced at execution time, not only displayed.

### Stage 13 — Quality/rework engine
**NOT YET COMPLETE**
```text
Worker output → independent QA → PASS → continue
                           ↓
                         REWORK → relevant worker/task → QA again
```
- Every rework records the exact problem.
- Maximum three reworks before escalation.
- QA worker must be independent from the producer.
- Manager owns final acceptance.

### Stage 14 — Multi-worker optimization
**NOT YET COMPLETE**
Compare combinations such as:
```text
Perplexity → Gemini → Local Validator
Gemini → Claude → Local Validator
Perplexity → Claude → Gemini → Local Validator
```
Consider task fit, quality, free availability, observed reliability, latency, failure history, dependencies and format compatibility.

### Stage 15 — Background execution
**NOT YET COMPLETE**
Background execution remains OFF by default and must be explicitly controllable.

## Current product status
**CURRENT STAGE: Stage 10 — Self-assessment v2 is the next required patch.**

Overall status:
```text
Core UI/backend                  ✅
Prompt analysis                 ✅
Workflow/decomposition          ✅
Worker registry/routing         ✅
Provider connector framework    ✅
Custom AI add                   ✅
Custom AI connection test       ✅
Groq real API validation        ✅
Groq NEXUS execution            ✅ / partially validated
Self-assessment                 ⚠️ PARTIAL
Artifact chaining               ⏳
Independent QA/rework           ⏳
Multi-worker optimization       ⏳
Background execution            ⏳
```

## Recent important fixes/commits
The recent Git history includes:
- `fix: validate compatible AI with real chat completion`
- `fix: make diagnostics UI-safe and match provider request headers`
- `fix: robustly parse compatible AI completion responses`
- `fix: make diagnosis fields React-safe primitives`

These fixes established the current working custom-provider/Groq diagnostic path.

## Development protocol
For every stage:
1. Read this file.
2. Inspect current repo.
3. Make one coherent stage.
4. Commit to GitHub.
5. Tell user exactly what to pull/run.
6. Test locally.
7. Inspect errors/screenshots/logs.
8. Fix before advancing.
9. Update this file with status.
10. Only then begin the next stage.

Do not silently restart the architecture or redo completed stages.

## Handoff
If a new chat starts, read `NEXUS_PROJECT_CONTEXT.md` first and continue from:

**Stage 10 — Self-assessment v2 is the next required patch; Groq custom AI connectivity and participation in real missions are already working.**

User preference: move quickly toward a working product, but keep changes coherent and test each stage before declaring it complete. Never fake provider quota, capability, connection or execution status.
