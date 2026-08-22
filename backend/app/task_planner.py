from __future__ import annotations

from .planner_models import PlanTask, TaskPlan
from .prompt_models import IntentAnalysis


def _add_task(tasks: list[PlanTask], task_id: str, title: str, task_type: str, *, deps: list[str] | None = None, inputs: list[str] | None = None, outputs: list[str] | None = None, workers: list[str] | None = None, quality_gate: bool = False, sprint: int = 1) -> None:
    tasks.append(PlanTask(task_id=task_id, title=title, task_type=task_type, dependencies=deps or [], inputs=inputs or [], outputs=outputs or [], preferred_worker_types=workers or [], quality_gate=quality_gate, sprint=sprint))


def build_task_plan(analysis: IntentAnalysis) -> TaskPlan:
    """NEXUS Manager: build an adaptive agile backlog; workers are selected dynamically at execution time."""
    tasks: list[PlanTask] = []
    if analysis.needs_research:
        _add_task(tasks, "research", "Research and source evidence", "research", outputs=["research_brief"], workers=["research", "ai"])
    if analysis.needs_file_analysis:
        _add_task(tasks, "file_analysis", "Inspect supplied files", "file_analysis", outputs=["file_analysis"], workers=["tool", "ai"])
    if analysis.needs_data_analysis:
        deps = [t.task_id for t in tasks if t.task_id in {"research", "file_analysis"}]
        inputs = (["research_brief"] if "research" in deps else []) + (["file_analysis"] if "file_analysis" in deps else [])
        _add_task(tasks, "data_analysis", "Analyse data and derive insights", "data_analysis", deps=deps, inputs=inputs, outputs=["analysis_findings"], workers=["data_analysis", "ai"])
    if analysis.needs_writing and not analysis.needs_presentation:
        _add_task(tasks, "writing", "Draft the requested written output", "writing", deps=[t.task_id for t in tasks], inputs=[x for t in tasks for x in t.outputs], outputs=["written_draft"], workers=["ai", "creative"])
    if analysis.needs_presentation:
        _add_task(tasks, "presentation", "Create the presentation", "presentation", deps=[t.task_id for t in tasks], inputs=[x for t in tasks for x in t.outputs], outputs=["presentation_draft"], workers=["ai", "creative"])
    if analysis.needs_image:
        _add_task(tasks, "image_generation", "Create the requested visual", "image_generation", deps=[t.task_id for t in tasks], inputs=[x for t in tasks for x in t.outputs], outputs=["image_output"], workers=["ai", "creative"])
    if analysis.needs_code:
        _add_task(tasks, "coding", "Implement the requested software work", "coding", deps=[t.task_id for t in tasks], inputs=[x for t in tasks for x in t.outputs], outputs=["code_output"], workers=["ai", "local"])
    if not tasks and "general_reasoning" in analysis.task_types:
        _add_task(tasks, "reasoning", "Reason through the requested task", "general_reasoning", outputs=["reasoning_output"], workers=["ai"])

    if tasks:
        deps = [t.task_id for t in tasks]
        inputs = [x for t in tasks for x in t.outputs]
        _add_task(tasks, "quality_review", "Independently review completed work", "quality_review", deps=deps, inputs=inputs, outputs=["quality_review"], workers=["ai", "validator"], quality_gate=True)

    notes = [
        "NEXUS Manager represents the user/CEO and owns objective interpretation, task decomposition, allocation, coordination, replanning, and final acceptance.",
        "Worker roles are dynamic: no worker is permanently assigned to research, writing, QA, or another corporate role. Every task is routed from its requirements, worker capabilities, live readiness, and task-specific evidence.",
        "Initial capability scores are onboarding priors. Existing workers retain their historical task performance; newly discovered workers receive onboarding records without resetting the existing workforce.",
        "Routing progressively trusts real task evidence as observations accumulate, while low-confidence workers remain eligible for controlled exploration.",
        "Quality review is itself a task. NEXUS dynamically selects the most suitable available worker to review the specific output; the reviewer recommends PASS or REWORK and the Manager makes the final decision.",
        "Rework creates a new employee task carrying the specific QA problem forward. At most three reworks are permitted before Manager escalation/stop.",
        "Employees may collaborate through artifact hand-offs, parallel independent work, peer support, and independent verification. Collaboration outcomes are recorded for future task-specific team selection.",
        "The Manager may replan an agile mission when new evidence, missing inputs, failures, or QA findings change the task requirements.",
    ]
    if analysis.needs_research and analysis.needs_presentation:
        notes.append("Research output is an input to presentation generation.")
    if analysis.needs_file_analysis and analysis.needs_presentation:
        notes.append("File analysis output is an input to presentation generation.")
    if analysis.needs_data_analysis and analysis.needs_presentation:
        notes.append("Analysis output is an input to presentation generation.")
    return TaskPlan(objective=analysis.objective, tasks=tasks, execution_order=[task.task_id for task in tasks], notes=notes, planner="local_graph_v4_dynamic_workforce_agile")
