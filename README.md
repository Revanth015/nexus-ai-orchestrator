# NEXUS

**Networked Execution & Unified AI Synthesis**

NEXUS is a **virtual corporate for the user**: the user acts as CEO, NEXUS acts as the Manager, and connected AI/tool workers act as employees. The Manager converts one business objective into an Agile workflow, allocates work to the right employees, coordinates artifact hand-offs, receives independent QA reports, and makes the final acceptance decision.

## Virtual corporate model

```text
User / CEO
   -> NEXUS Manager
      -> understand objective
      -> create Agile sprint backlog
      -> assign tasks to employees
      -> coordinate dependencies and hand-offs
      -> receive employee outputs
      -> send completed work to QA Employee
      -> receive QA recommendation
      -> make final ACCEPT / REWORK decision

AI / Tool Employees
   -> execute assigned work
   -> produce artifacts
   -> consume upstream hand-offs

QA Employee
   -> independently checks quality
   -> records the specific problem when work fails
   -> recommends PASS or REWORK
   -> never owns the final acceptance decision
```

If QA recommends rework, the Manager creates a **new rework task** and assigns it to an employee. The QA problem statement is carried into that task so the employee knows what must be corrected. A mission allows **at most three rework cycles**; after the third failed review, the Manager stops the mission rather than looping indefinitely.

## Core principles

- **Manager-owned orchestration:** NEXUS owns planning, allocation, coordination, review decisions, and final acceptance.
- **Employee separation:** AI workers execute assigned jobs; they do not become the Manager merely because they have stronger reasoning capability.
- **Independent QA:** quality review is a separate employee responsibility.
- **Agile execution:** missions are sprint-like task backlogs with dependencies, inputs, outputs, hand-offs, review gates, and rework cycles.
- **Free-first:** NEXUS must never silently incur a paid AI/API charge.
- **Task-first routing:** understand the task before selecting an employee.
- **Inter-agent handoffs:** one employee's structured output can become another employee's input.
- **Quality-first:** meaningful output is independently reviewed and reworked when material issues remain.
- **Fault tolerant:** quota/rate-limit/failure events trigger checkpointed failover to another safe employee.
- **Human controlled:** the CEO can pause or stop execution.
- **Local-first:** deterministic tools and local models are preferred where practical.

## Corporate workflow

```text
CEO objective
  -> Manager intent understanding
  -> Agile task decomposition
  -> dependency / hand-off graph
  -> free-resource check
  -> employee allocation
  -> employee execution
  -> artifact hand-offs
  -> independent QA employee
  -> QA problem + PASS/REWORK recommendation
  -> Manager final decision
  -> ACCEPT or new employee rework task
  -> maximum 3 rework cycles
  -> final corporate result
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

## Current employee roles

- **Gemini:** general AI employee
- **Claude:** reasoning/coding/document employee when connected and eligible
- **Perplexity:** research employee when connected and eligible
- **NEXUS Local Tools:** deterministic execution employee
- **NEXUS Quality Review Employee:** independent QA employee

NEXUS itself is the Manager; it is not selected as an employee worker.

## Stack

- Frontend: React + Vite
- Backend: Python + FastAPI
- Data: Pandas, NumPy, OpenPyXL
- Artifacts: python-pptx, python-docx, PDF tooling
- Git: Git + GitHub

## Development status

Virtual-corporate Agile orchestration is the primary product architecture. Worker connectors and specialized capabilities are added behind the Manager/Employee interface.
