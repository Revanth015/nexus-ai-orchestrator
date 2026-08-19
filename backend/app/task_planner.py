from __future__ import annotations

from .planner_models import PlanTask, TaskPlan
from .prompt_models import IntentAnalysis


def _add_task(tasks: list[PlanTask], task_id: str, title: str, task_type: str, *, deps: list[str] | None = None, inputs: list[str] | None = None, outputs: list[str] | None = None, workers: list[str] | None = None, quality_gate: bool = False) -> None:
    tasks.append(
        PlanTask(
            task_id=task_id,
            title=title,
            task_type=task_type,
            dependencies=deps or [],
            inputs=inputs or [],
            outputs=outputs or [],
            preferred_worker_types=workers or [],
            quality_gate=quality_gate,
        )
    )


def build_task_plan(analysis: IntentAnalysis) -> TaskPlan:
    """Build a deterministic DAG from the Stage 2 intent.

    No external AI is used. The planner only turns the already-understood
    intent into explicit tasks, artifacts, and dependency edges.
    """
    tasks: list[PlanTask] = []

    if analysis.needs_research:
        _add_task(
            tasks, "research", "Research and source evidence", "research",
            outputs=["research_brief"], workers=["research"],
        )

    if analysis.needs_file_analysis:
        _add_task(
            tasks, "file_analysis", "Inspect supplied files", "file_analysis",
            outputs=["file_analysis"], workers=["tool", "data_analysis"],
        )

    if analysis.needs_data_analysis:
        deps = [t.task_id for t in tasks if t.task_id in {"research", "file_analysis"}]
        inputs = ["research_brief"] if "research" in deps else []
        if "file_analysis" in deps:
            inputs.append("file_analysis")
        _add_task(
            tasks, "data_analysis", "Analyse data and derive insights", "data_analysis",
            deps=deps, inputs=inputs, outputs=["analysis_findings"],
            workers=["data_analysis", "ai"],
        )

    if analysis.needs_writing and not analysis.needs_presentation:
        deps = [t.task_id for t in tasks]
        inputs = [x for t in tasks for x in t.outputs]
        _add_task(
            tasks, "writing", "Draft the requested written output", "writing",
            deps=deps, inputs=inputs, outputs=["written_draft"],
            workers=["ai", "creative"],
        )

    if analysis.needs_presentation:
        deps = [t.task_id for t in tasks]
        inputs = [x for t in tasks for x in t.outputs]
        _add_task(
            tasks, "presentation", "Create the presentation", "presentation",
            deps=deps, inputs=inputs, outputs=["presentation_draft"],
            workers=["creative", "ai"],
        )

    if analysis.needs_image:
        deps = [t.task_id for t in tasks]
        inputs = [x for t in tasks for x in t.outputs]
        _add_task(
            tasks, "image_generation", "Create the requested visual", "image_generation",
            deps=deps, inputs=inputs, outputs=["image_output"],
            workers=["creative", "ai"],
        )

    if analysis.needs_code:
        deps = [t.task_id for t in tasks]
        inputs = [x for t in tasks for x in t.outputs]
        _add_task(
            tasks, "coding", "Implement the requested software work", "coding",
            deps=deps, inputs=inputs, outputs=["code_output"],
            workers=["ai", "local"],
        )

    # Quality review is always a terminal gate unless the user explicitly
    # disabled it in Stage 2.
    if analysis.needs_quality_review:
        deps = [t.task_id for t in tasks]
        inputs = [x for t in tasks for x in t.outputs]
        _add_task(
            tasks, "quality_review", "Review the work and decide PASS or REWORK", "quality_review",
            deps=deps, inputs=inputs, outputs=["quality_review"],
            workers=["validator", "ai"], quality_gate=True,
        )

    execution_order = [task.task_id for task in tasks]
    notes: list[str] = [
        "Tasks are planned locally; no AI worker has been called.",
        "A dependency means the upstream task must produce its artifact before the downstream task can run.",
    ]
    if analysis.needs_research and analysis.needs_presentation:
        notes.append("Research output is an input to presentation generation.")
    if analysis.needs_file_analysis and analysis.needs_presentation:
        notes.append("File analysis output is an input to presentation generation.")
    if analysis.needs_quality_review:
        notes.append("Quality review is the final gate; REWORK will later route back to the affected task.")

    return TaskPlan(
        objective=analysis.objective,
        tasks=tasks,
        execution_order=execution_order,
        notes=notes,
    )
