# NEXUS Engineering Hardening Baseline

## Purpose

This document records the engineering hardening completed after the initial MVP architecture review. It is the baseline for future NEXUS development; new features should not bypass these runtime contracts.

## Runtime contracts now enforced

### Executor-aware routing

A worker is not considered task-eligible merely because its capability score is high. The routing layer checks the concrete runtime executor supported by that worker. Current text AI workers support text task execution; local tools support data/file analysis; the local validator is reserved for quality review.

### Automatic failover

Task execution now records a failed worker, excludes it from the current attempt, and re-routes to the next safe execution-ready worker when fallback is enabled. A task response exposes `attempts`, `fallback_used`, and `failed_worker_ids`.

### Free-first policy

Free-only routing continues to require an explicit free-status category accepted by NEXUS. User-declared free status is not presented as provider-verified free status. Exact remaining quota is never fabricated.

### Manager verification

The Manager decision contains verification requirements. When a mission already has an independent quality-review task, that QA gate is the verification mechanism rather than issuing a duplicate verification call for the same work.

### Structured QA

QA prompts request JSON with score, decision, problem, and severity. The runtime still accepts the legacy text format as a compatibility fallback, so older providers do not break the mission pipeline.

### Rework

QA `REWORK` creates a new task with a new task ID and carries the specific QA problem into the rework prompt. A new independent QA task is created for each rework cycle. The maximum remains three cycles.

### Artifact hand-offs

Artifacts now carry an ID, source task, type, version and content. Downstream tasks consume named upstream outputs only when their declared dependencies have completed.

### Resource accounting

The mission response reports actual execution calls consumed, including fallback attempts and collaborators. The mission memory service uses that actual value rather than summing Manager estimates a second time.

### Custom AI lifecycle

Custom employees support add, test/diagnose, update, enable/disable and delete. Any configuration update invalidates the previous successful connection test. Credentials are never returned in public worker data.

### File safety

Uploads reject unsafe file IDs, keep internal storage paths out of API responses, preserve original filenames in local metadata, and explicitly report when extracted content is truncated.

### Durable local writes

Local JSON operational stores use atomic replacement and re-entrant locks. This reduces partial-write corruption during normal local operation. SQLite remains the next persistence upgrade when multi-process/concurrent mission execution becomes a requirement.

### Learning

Task performance now includes observation-based confidence and a recency factor. Collaboration outcomes can be recorded and queried rather than always returning zero evidence.

### Regression protection

Backend unit tests cover executor-aware routing, free-only exclusion, automatic failover and explicit no-fallback behavior. GitHub Actions compiles/imports the backend, runs pytest, and builds the React frontend on pushes and pull requests.

## Known intentional limits

- Current remote providers are text-chat executors; image generation and native vision execution are not falsely advertised by the runtime.
- File extraction remains bounded for predictable local resource use; truncation is surfaced in metadata.
- JSON stores are still local single-install storage. They are not a distributed database.
- Background execution remains disabled by default.
- Provider free eligibility still requires explicit evidence; NEXUS does not claim an exact remaining quota when the provider does not expose it.

## Engineering rule

Before adding another major capability, preserve this sequence:

`build → pull → run → test → fix → advance`

No new feature is considered complete until the regression suite and the relevant end-to-end workflow pass.
