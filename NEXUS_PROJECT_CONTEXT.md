# NEXUS — Project Context & Stage Tracker

> Read this file first in every new NEXUS development chat. Continue from the current stage; do not restart the architecture discussion.

## Project
- Name: NEXUS — AI Orchestrator
- Repository: `Revanth015/nexus-ai-orchestrator`
- Local path: `D:\Projects\nexus-ai-orchestrator`
- Goal: corporate-ready, free-first multi-AI orchestration. User gives one prompt; NEXUS understands it, decomposes it, selects suitable workers, connects outputs to downstream tasks, quality-checks results, reworks when needed, and immediately falls back when a worker is unavailable/quota-limited.

## Non-negotiable requirements
1. Free AI only; never silently use paid APIs/models.
2. Never invent exact remaining quota.
3. If quota is not exposed, mark it unknown and estimate only from observed telemetry, rate-limit/quota errors and reset information when observable.
4. Immediate fallback on quota, rate-limit, authentication, temporary or recoverable connector failures.
5. Free-first routing.
6. Background execution must be controllable and default OFF.
7. Adding a new AI/provider should be easy and isolated from the orchestration core.
8. Quality checks must be applied to substantial outputs; rework until satisfactory or only non-material issues remain.
9. NEXUS should compare/mix multiple worker combinations for difficult tasks.
10. Never commit API keys/secrets.
11. Build in stages: build → pull → run → test → fix → only then advance.

## Runtime
- Windows
- Python 3.11.2
- Node 24.18.0
- npm 11.x; use `npm.cmd` because PowerShell blocks `npm.ps1`
- Backend: FastAPI/Uvicorn
- Frontend: React/Vite
- Frontend: `http://localhost:5173/`
- Backend: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`
- venv: `backend\.venv`
- CMD activation: `backend\.venv\Scripts\activate.bat`

## Stages

### Stage 1 — Base interface/backend
**PASSED**
- React/Vite UI works.
- FastAPI works.
- Frontend/backend health communication works.
- `System ready`, Free-only and Background-off states work.

### Stage 2 — Prompt understanding
**PASSED**
- Local deterministic analyzer; no external AI used.
- Detects research, file analysis, data analysis, writing, presentation, image generation, coding, current information and quality review.
- Detects semantic visual terms including infographic, diagram, visual, illustration, poster, graphic, flowchart, mind map, concept art, banner and thumbnail.
- Detects deliverables, requirements and dependencies.
- Confidence is heuristic, not true AI confidence; later it should be cross-validated with AI-assisted interpretation.

### Stage 3 — Task decomposition/workflow graph
**PASSED**
Creates tasks with IDs, types, titles, dependencies, inputs, outputs, status and quality gates.

Validated example:
```text
1 Research → research_brief
2 File analysis → file_analysis
3 Data analysis ← research_brief + file_analysis → analysis_findings
4 Presentation ← research_brief + file_analysis + analysis_findings → presentation_draft
5 Quality review ← all previous artifacts → PASS/REWORK quality gate
```
This must remain a dependency graph, not a flat list.

### Stage 4 — Worker registry + capability routing
**PASSED**
Current conceptual workers:
- Perplexity — research
- Gemini — general/multimodal/presentation
- Claude — reasoning/coding/documents
- NEXUS Local Tools
- NEXUS Local Validator

Routing distinguishes:
```text
Preferred profile = best worker for the task if connected/available
Current execution = worker NEXUS can actually execute now
```
Example validated in UI:
```text
Research: preferred Perplexity, current execution Local Tools
Presentation: preferred Gemini, current execution Local Tools
```
Unconnected workers are not presented as executable. Scores are capped at 100. Policy: `free_first_execution_aware_v2`.

## Stage 5 — Gemini connector
**BUILT — PENDING USER LOCAL TEST**

The first real connector is Gemini through Google's official `google-genai` Python SDK.

Files/changes:
- `backend/app/gemini_connector.py` — connector + telemetry + failure classification
- `backend/.env.example` — local secret template
- `backend/requirements.txt` — `google-genai` dependency
- `backend/app/main.py` — Gemini status/test endpoints
- `backend/app/worker_registry.py` — live Gemini readiness overlay

### Free-only policy for Stage 5
- Default model: `gemini-3.1-flash-lite`.
- This model is in NEXUS's verified-free allowlist for this stage based on the current Google Gemini API pricing documentation checked during development.
- Connector rejects a model outside the verified-free allowlist.
- No paid model is automatically selected.
- Connector never calls Gemini automatically at backend startup; the test is explicit.

### Connector telemetry
Tracks:
- configured/authentication state
- execution readiness
- observed requests
- successes/failures
- last success/failure
- latency
- failure class
- quota status

Failure classes include:
- authentication
- quota
- rate_limit
- temporary
- provider_error

Exact remaining quota is never fabricated. Current exact quota is unknown unless a provider exposes it.

### Stage 5 endpoints
```text
GET  http://127.0.0.1:8000/connectors/gemini/status
POST http://127.0.0.1:8000/connectors/gemini/test
```
The POST test makes one real model call only when explicitly invoked.

### Stage 5 user test
After pulling:
```cmd
cd D:\Projects\nexus-ai-orchestrator
cd backend
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
```
Edit `backend\.env` and set:
```text
GEMINI_API_KEY=YOUR_REAL_KEY
```
Never commit `.env` or the key.

Start:
```cmd
uvicorn app.main:app --reload
```
Check status first:
```text
http://127.0.0.1:8000/connectors/gemini/status
```
Then explicitly POST the test request. The test should return Gemini text and then the worker registry should show Gemini as connected/execution-ready.

**Do not mark Stage 5 passed until the user performs this local test successfully.**

## Current frontend
After prompt submission it shows:
1. NEXUS INTENT
2. NEXUS WORKFLOW
3. NEXUS WORKER MAP

Current frontend calls:
- `/health`
- `/analyze`
- `/plan`
- `/route/{task_type}`

Gemini connector controls are not yet exposed in the UI; Stage 5 backend validation comes first.

## Known fixes
- npm PowerShell issue: use `npm.cmd`.
- Temporary npm TLS certificate issue was resolved by changing Wi-Fi; do not permanently disable SSL verification.
- Stage 4 frontend break fixed by importing `createRoot` from `react-dom/client`.

## Next stages after Gemini validation
1. Add real fallback execution and quota/rate-limit routing.
2. Add Perplexity connector.
3. Add Claude connector.
4. Connect task artifacts so worker output becomes downstream worker input.
5. Add real execution-state UI.
6. Add quality/rework engine.
7. Add multi-combination optimization.
8. Add background execution with explicit ON/OFF controls.
9. Add easier worker/provider configuration.

## Future quality engine
Classify output and validate appropriately:
- Research: factual/source quality
- Data: calculations/assumptions/consistency
- PPT: narrative/evidence/slide structure/readability/factual consistency
- Reports: structure/evidence/logic/completeness/writing
- Images: prompt adherence/visual clarity/label correctness
- Code: syntax/tests/functional requirements

Quality loop:
```text
Worker output → Quality evaluator → PASS → final
                         ↓
                       REWORK → relevant task/worker → review again
```
Stop when satisfactory or only non-material issues remain; avoid endless retries.

## Future multi-worker optimization
NEXUS should compare combinations such as:
```text
Perplexity → Gemini → Local Validator
Gemini → Claude → Local Validator
Perplexity → Claude → Gemini → Local Validator
```
Consider task fit, output quality, free availability, estimated resource remaining, reliability, latency, failure history, dependency compatibility and output-format compatibility.

## Background requirement
Background execution must remain controllable and default OFF. Future UI states: ON / OFF / paused / stopped. Never implement uncontrolled background work.

## Development protocol
For every stage:
1. Read this file.
2. Inspect current repo.
3. Make one coherent stage.
4. Commit to GitHub.
5. Tell user exactly what to pull/run.
6. Test locally.
7. Inspect errors/screenshots.
8. Fix before advancing.
9. Update this file with status.
10. Only then begin next stage.

## Handoff
If a new chat starts, read `NEXUS_PROJECT_CONTEXT.md` first and continue from **Current stage: Stage 5 — Gemini connector built, pending local test**. Do not restart the architecture discussion.

User preferences: step-by-step; one stage at a time; test every stage; no huge untested batches; zero-cost/free AI; clear external actions; direct GitHub updates when appropriate; never fake quota/capability claims.
