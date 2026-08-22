from __future__ import annotations

from .planner_models import PlanTask, TaskPlan
from .prompt_models import IntentAnalysis


def _add_task(tasks: list[PlanTask], task_id: str, title: str, task_type: str, *, deps: list[str] | None = None, inputs: list[str] | None = None, outputs: list[str] | None = None, workers: list[str] | None = None, quality_gate: bool = False, sprint: int = 1) -> None:
    tasks.append(PlanTask(task_id=task_id, title=title, task_type=task_type, dependencies=deps or [], inputs=inputs or [], outputs=outputs or [], preferred_worker_types=workers or [], quality_gate=quality_gate, sprint=sprint))


def build_task_plan(analysis: IntentAnalysis) -> TaskPlan:
    """NEXUS Manager planning layer: create an agile task backlog and worker hand-offs locally."""
    tasks: list[PlanTask] = []
    if analysis.needs_research:
        _add_task(tasks, "research", "Research and source evidence", "research", outputs=["research_brief"], workers=["research"])
    if analysis.needs_file_analysis:
        _add_task(tasks, "file_analysis", "Inspect supplied files", "file_analysis", outputs=["file_analysis"], workers=["tool", "data_analysis"])
    if analysis.needs_data_analysis:
        deps = [t.task_id for t in tasks if t.task_id in {"research", "file_analysis"}]
        inputs = (["research_brief"] if "research" in deps else []) + (["file_analysis"] if "file_analysis" in deps else [])
        _add_task(tasks, "data_analysis", "Analyse data and derive insights", "data_analysis", deps=deps, inputs=inputs, outputs=["analysis_findings"], workers=["data_analysis", "ai"])
    if analysis.needs_writing and not analysis.needs_presentation:
        _add_task(tasks, "writing", "Draft the requested written output", "writing", deps=[t.task_id for t in tasks], inputs=[x for t in tasks for x in t.outputs], outputs=["written_draft"], workers=["ai", "creative"])
    if analysis.needs_presentation:
        _add_task(tasks, "presentation", "Create the presentation", "presentation", deps=[t.task_id for t in tasks], inputs=[x for t in tasks for x in t.outputs], outputs=["presentation_draft"], workers=["creative", "ai"])
    if analysis.needs_image:
        _add_task(tasks, "image_generation", "Create the requested visual", "image_generation", deps=[t.task_id for t in tasks], inputs=[x for t in tasks for x in t.outputs], outputs=["image_output"], workers=["creative", "ai"])
    if analysis.needs_code:
        _add_task(tasks, "coding", "Implement the requested software work", "coding", deps=[t.task_id for t in tasks], inputs=[x for t in tasks for x in t.outputs], outputs=["code_output"], workers=["ai", "local"])
    if not tasks and "general_reasoning" in analysis.task_types:
        _add_task(tasks, "reasoning", "Reason through the requested task", "general_reasoning", outputs=["reasoning_output"], workers=["ai"])

    # Agile Definition of Done: every mission is reviewed by a separate employee.
    # The reviewer recommends PASS/REWORK; the Manager owns the final decision.
    if tasks:
        deps = [t.task_id for t in tasks]
        inputs = [x for t in tasks for x in t.outputs]
        _add_task(tasks, "quality_review", "Independent quality review", "quality_review", deps=deps, inputs=inputs, outputs=["quality_review"], workers=["validator", "ai"], quality_gate=True)

    notes = [
        "NEXUS Manager decomposes the user's objective locally before any employee is called.",
        "Tasks are treated as an agile sprint backlog with dependencies, inputs, outputs, and worker allocation at execution time.",
        "Employees produce artifacts; downstream employees consume those artifacts.",
        "A separate Quality Review Employee reviews the Definition of Done and reports PASS or REWORK to the Manager.",
        "The Manager owns the final ACCEPT/REWORK decision and can create a new rework task for the appropriate employee.",
    ]
    if analysis.needs_research and analysis.needs_presentation:
        notes.append("Research output is an input to presentation generation.")
    if analysis.needs_file_analysis and analysis.needs_presentation:
        notes.append("File analysis output is an input to presentation generation.")
    if analysis.needs_data_analysis and analysis.needs_presentation:
        notes.append("Analysis output is an input to presentation generation.")
    return TaskPlan(objective=analysis.objective, tasks=tasks, execution_order=[task.task_id for task in tasks], notes=notes, planner="local_graph_v2_agile")
