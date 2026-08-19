# NEXUS

**Networked Execution & Unified AI Synthesis**

NEXUS is a free-first AI orchestration workspace designed to turn one user objective into a coordinated workflow across AI workers, local tools, research resources, and artifact generators.

## Core principles

- **Free-first:** NEXUS must never silently incur a paid AI/API charge.
- **Task-first routing:** understand the task before selecting a worker.
- **Inter-agent handoffs:** one task's structured output can become another task's input.
- **Quality-first:** every meaningful output is validated and reworked when material issues remain.
- **Fault tolerant:** quota/rate-limit/failure events trigger checkpointed failover to another safe worker.
- **Adaptive:** NEXUS records worker and workflow performance and improves future routing.
- **Human controlled:** background execution can be paused or stopped at any time.
- **Local-first:** deterministic tools and local models are preferred where practical.

## Planned V1 stack

- Frontend: React + TypeScript
- Backend: Python + FastAPI
- Database: SQLite
- AI gateway: LiteLLM OSS
- Local models: Ollama
- Data: Pandas, NumPy, OpenPyXL
- Artifacts: python-pptx, python-docx, PDF tooling
- Git: Git + GitHub

## Product flow

```text
User prompt
  -> intent understanding
  -> task decomposition
  -> workflow/dependency graph
  -> free-resource check
  -> worker routing
  -> execution + handoffs
  -> quality validation
  -> rework/failover when needed
  -> learning/update
  -> final answer or artifact
```

## Free-only safety model

A worker can be:

- `VERIFIED_FREE`
- `MEASURED_FREE`
- `ESTIMATED_FREE`
- `UNKNOWN`
- `PAID`
- `EXHAUSTED`

Unknown or paid workers are not automatically selected in Free-Only mode.

## Development status

Repository initialized. V1 foundation is being built incrementally.
