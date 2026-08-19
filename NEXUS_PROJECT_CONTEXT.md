# NEXUS — Project Context & Stage Tracker

> **Purpose:** Persistent handoff document for future development sessions. Read this file before making architectural changes so the current project state, constraints, decisions, and next stage are clear.

## 1. Project identity

**Name:** NEXUS — AI Orchestrator

**Repository:** `Revanth015/nexus-ai-orchestrator`

**Local path used by developer:** `D:\Projects\nexus-ai-orchestrator`

**Primary goal:** Build a corporate-ready, free-first multi-AI orchestration system. The user gives NEXUS one natural-language request. NEXUS understands it, decomposes it into tasks, maps each task to the most suitable AI/tool, connects outputs between tasks, validates quality, retries/reworks when necessary, and falls back to another worker when a preferred AI is unavailable or reaches a quota/resource limit.

## 2. Core product vision

NEXUS is intended to act as a bridge between the user and multiple AI systems rather than as another single chatbot.

The intended flow is:

```text
User prompt
    ↓
NEXUS understands intent
    ↓
Task decomposition
    ↓
Task/dependency graph
    ↓
Capability + free-resource aware routing
    ↓
Execute workers
    ↓
Pass outputs as inputs to downstream workers
    ↓
Quality review
    ↓
PASS → final output
REWORK → relevant task(s) again
FAIL / QUOTA → immediate fallback worker
```

Examples:
- Perplexity research output can become Gemini presentation input.
- File analysis can feed data analysis.
- Research + analysis + files can feed PPT generation.
- Final presentation can pass through a quality gate.
- Image, code, report, spreadsheet, research, presentation and other task types should eventually be supported.

## 3. Hard product constraints

1. **Free AI only.** Do not design the system around paid APIs or paid model access.
2. **No fake quota values.** If a provider exposes an actual quota/usage value, use it. If not, mark quota as unknown and estimate only from observed telemetry.
3. **Unknown quota must be handled gracefully.** NEXUS should predict/estimate availability from observed usage, failures, rate limits and responses when exact remaining quota is unavailable.
4. **Immediate fallback.** If a selected AI fails because of quota, rate limit, authentication, temporary availability, or another recoverable connector failure, NEXUS should reroute to the best eligible fallback instead of getting stuck.
5. **Free-first routing.** Paid/exhausted workers must not be selected when free-only mode is enabled.
6. **Background execution must be controllable.** The UI must provide a way to stop/disable background operation when NEXUS is not in use.
7. **Easy worker addition.** Adding a new AI/provider should require minimal configuration and should not require rewriting the orchestration core.
8. **Quality matters.** Every substantial task should have an appropriate quality check. NEXUS should iterate/rework until the result is acceptable, or stop when only minor issues remain that do not materially affect the requested outcome.
9. **Multiple combinations.** NEXUS should be able to compare/mix worker combinations rather than always using one fixed AI per task type.
10. **No secrets in Git.** API keys/tokens must stay in local environment/config files ignored by Git.
11. **Stage-by-stage development.** After every meaningful build stage, run the program and test before adding the next major capability. Do not dump large batches of untested changes.

## 4. Current technology/runtime

- OS: Windows
- IDE: Visual Studio / VS Code-style workflow as used by developer
- Python: 3.11.2
- Node: 24.18.0
- npm: 11.x, invoked as `npm.cmd` because PowerShell execution policy blocks `npm.ps1`
- Backend: Python + FastAPI/Uvicorn
- Frontend: React + Vite
- Repository branch: `main`
- Frontend local URL: `http://localhost:5173/`
- Backend local URL: `http://127.0.0.1:8000/`
- Backend health: `http://127.0.0.1:8000/health`
- Python virtual environment: `backend\.venv`
- Activation from CMD: `backend\.venv\Scripts\activate.bat`

## 5. Important local setup notes

PowerShell execution policy caused:

```text
npm.ps1 cannot be loaded because running scripts is disabled
```

Use `npm.cmd` in CMD/terminal commands.

There was also a temporary npm TLS/certificate problem (`UNABLE_TO_VERIFY_LEAF_SIGNATURE`) caused by the local network certificate chain. A later Wi-Fi change allowed npm installation to work. Do not disable SSL verification as a permanent solution.

## 6. Architecture already implemented

### Stage 1 — Base interface + backend connection
**Status: PASSED**

Verified:
- React frontend loads.
- FastAPI backend runs.
- Frontend/backend health communication works.
- UI shows `System ready` when backend is available.
- Free-only mode is visible.
- Background execution is currently off by default.

### Stage 2 — Prompt understanding
**Status: PASSED**

Implemented deterministic local first-pass analyzer.

Current analyzer concept:
- No external AI call.
- Detects task types.
- Detects deliverables.
- Detects requirements.
- Detects dependencies.
- Detects current-information needs.
- Detects research/file/data/presentation/image/code/writing needs.
- Adds quality review by default unless explicitly disabled.
- Handles semantic visual terms such as infographic, diagram, visual, illustration, poster, graphic, flowchart, mind map, concept art, banner, thumbnail, etc.

Important current limitation:
- The displayed confidence is heuristic, not true AI confidence. Later it should be combined with AI-assisted interpretation and cross-validation.

### Stage 3 — Task decomposition / workflow graph
**Status: PASSED**

NEXUS now creates executable task plans with:
- task ID
- task type
- title
- dependencies
- inputs
- outputs
- status
- quality gate

Validated example:

```text
1. Research and source evidence
      → research_brief
2. Inspect supplied files
      → file_analysis
3. Analyse data and derive insights
      inputs: research_brief, file_analysis
      → analysis_findings
4. Create the presentation
      inputs: research_brief, file_analysis, analysis_findings
      → presentation_draft
5. Review the work and decide PASS or REWORK
      inputs: research_brief, file_analysis, analysis_findings, presentation_draft
      → quality gate
```

This dependency graph is a core NEXUS feature and must not be replaced with a simple flat prompt list.

### Stage 4 — Worker registry + capability routing
**Status: PASSED**

Implemented worker profiles and capability-based routing.

Current conceptual workers include:
- Perplexity — research-oriented
- Gemini — general/multimodal/presentation-oriented
- Claude — reasoning/coding/document-oriented
- NEXUS Local Tools
- NEXUS Local Validator

Each worker has capability/reliability/efficiency/resource metadata.

Routing separates two concepts:

```text
Preferred profile
= best worker for the task if connected/available

Current execution
= worker NEXUS can actually execute right now
```

This distinction was explicitly validated in the UI.

Example:

```text
Research
Preferred profile: perplexity
Current execution: local-tools

Presentation
Preferred profile: gemini
Current execution: local-tools
```

Unconnected workers are displayed as `not connected` rather than being falsely presented as executable.

Scores are capped at 100.

Current routing policy label:
`free_first_execution_aware_v2`

Quota values are currently unknown until live connectors/telemetry are added.

## 7. Current frontend behavior

The main UI currently displays, after prompt submission:

1. **NEXUS INTENT** — request analysis
2. **NEXUS WORKFLOW** — execution plan
3. **NEXUS WORKER MAP** — capability-based routing

The UI currently fetches:
- `/health`
- `/analyze`
- `/plan`
- `/route/{task_type}`

The worker map displays:
- task title
- capability
- current execution worker
- preferred profile when different
- top candidate workers and scores
- ready/not-connected status

## 8. Recent bug fixed

Stage 4 temporarily broke the frontend because `createRoot` was used without importing it from `react-dom/client` in `frontend/src/main.jsx`.

It was fixed by adding:

```js
import { createRoot } from "react-dom/client";
```

The normal NEXUS interface was then restored and Stage 4 was revalidated.

## 9. Current project status

### COMPLETED

- [x] Git repository connected
- [x] Local clone working
- [x] Backend virtual environment
- [x] FastAPI health endpoint
- [x] React/Vite interface
- [x] Frontend/backend connection
- [x] Free-only mode indicator
- [x] Background-off state indicator
- [x] Prompt intent analysis
- [x] Semantic image/task detection
- [x] Task decomposition
- [x] Dependency-aware workflow graph
- [x] Worker registry
- [x] Capability mapping
- [x] Preferred worker vs executable worker distinction
- [x] Free-first routing
- [x] Fallback candidate representation
- [x] Unknown quota representation

### NOT YET IMPLEMENTED / NEXT

**Stage 5 — Real free AI connectors** is the next major stage.

Do NOT assume it has started merely because the worker profiles exist.

Planned order:
1. Add first real free connector (initial candidate: Gemini, subject to verifying current free-access mechanism before implementation).
2. Keep credentials local and out of Git.
3. Test one simple request.
4. Record telemetry.
5. Mark worker connected/executable only after successful test.
6. Add failure/quota handling.
7. Then add Perplexity connector.
8. Then add Claude connector.
9. Validate routing/fallback with real workers.

## 10. Stage 5 connector requirements

Each connector should expose, as far as legitimately observable:

```text
provider
connected
free_only
execution_ready
authentication_status
quota_status
quota_exact_or_unknown
quota_estimate
usage_observed
last_success
last_failure
failure_reason
latency
model/capability metadata
```

Never invent exact remaining quota.

If the provider does not expose remaining quota, use:

```text
unknown exact quota
+
observed usage
+
rate-limit/quota errors
+
request success/failure history
+
reset-window information if observable
```

to estimate availability.

## 11. Future quality engine

The final system should classify the requested output and apply appropriate checks:

- Information/research → factual/source quality
- Data analysis → calculations, assumptions, consistency
- Presentation → narrative, evidence, slide structure, readability, factual consistency
- Report → structure, evidence, logic, completeness, writing quality
- Image → prompt adherence, visual clarity, correctness of labels/content when applicable
- Code → syntax/tests, functional behavior, requirements coverage

Quality loop concept:

```text
Worker output
   ↓
Quality evaluator(s)
   ↓
PASS ─────────────→ final
   │
 REWORK
   ↓
Relevant task/worker
   ↓
Quality check again
```

The system should avoid endless retries. Stop on a satisfactory result or a result with only non-material/minor issues according to the configured threshold.

## 12. Future multi-worker optimization

NEXUS should eventually compare multiple viable worker combinations for difficult jobs.

Example:

```text
Option A:
Perplexity → Gemini → Local Validator

Option B:
Gemini → Claude → Local Validator

Option C:
Perplexity → Claude → Gemini → Local Validator
```

The selection should consider:
- task fit
- output quality
- free availability
- estimated resource remaining
- reliability
- latency
- failure history
- dependency compatibility
- output format compatibility

## 13. Background execution requirement

NEXUS should eventually support background operation but must allow the user to turn it off when not in use.

Future UI should make the state explicit:
- Background ON
- Background OFF
- paused/stopped

Do not implement uncontrolled background execution.

## 14. Corporate-ready direction

The UI should remain smooth and professional but should not become over-engineered. The user explicitly prefers staged, practical development and easy debugging over a huge first release.

Important UX principle:

> The user should be able to understand what NEXUS is doing without seeing unnecessary technical complexity.

Useful visible execution states later:

```text
Understanding prompt…
Building task plan…
Selecting workers…
Waiting for research…
Passing research to presentation worker…
Quality checking…
Reworking…
Fallback triggered…
Completed…
```

## 15. Development protocol

For every future stage:

1. Read this file.
2. Inspect the current repository before changing architecture.
3. Make one coherent stage of changes.
4. Commit changes to GitHub.
5. Tell the user exactly what to pull/run.
6. Run/test locally with the user.
7. Inspect screenshots/errors.
8. Fix failures before advancing.
9. Update this context file with the new stage/status.
10. Only then start the next stage.

Do not stack multiple untested stages.

## 16. Immediate next action

**Before Stage 5 implementation:** verify the current repository state and decide the safest real free Gemini connection method available to the user's environment. Do not assume an API is free merely because a consumer Gemini account is free. Verify the actual connector/access mechanism before asking the user to configure credentials.

## 17. Handoff instruction for a new chat

If a new conversation starts, the assistant should read `NEXUS_PROJECT_CONTEXT.md` first and continue from the **Current project status** section rather than restarting the architecture discussion.

The user prefers:
- step-by-step instructions
- one build stage at a time
- test after every stage
- no large untested batch of changes
- zero-cost/free AI wherever possible
- clear external actions when the user must do something locally
- direct GitHub repository updates when appropriate
- no fake claims about AI quota or capabilities
