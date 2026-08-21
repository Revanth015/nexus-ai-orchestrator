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
    """Build the NEXUS manager's deterministic task graph.

    The manager decomposes the objective, defines artifact hand-offs, and
    places a terminal QA employee on multi-task missions. No AI worker is
    called while planning.
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

    if not tasks and "general_reasoning" in analysis.task_types:
        _add_task(
            tasks,
            "reasoning",
            "Reason through the requested task",
            "general_reasoning",
            outputs=["reasoning_output"],
            workers=["ai"],
        )

    # The manager owns the final gate. Any mission containing multiple worker
    # tasks gets QA even when the user did not explicitly say "review".
    # Single-task jobs retain the explicit user-requested review behavior.
    add_quality_gate = analysis.needs_quality_review or len(tasks) > 1
    if add_quality_gate and not any(task.task_id == "quality_review" for task in tasks):
        deps = [t.task_id for t in tasks]
        inputs = [x for t in tasks for x in t.outputs]
        _add_task(
            tasks,
            "quality_review",
            "Review the work and decide PASS or REWORK",
            "quality_review",
            deps=deps,
            inputs=inputs,
            outputs=["quality_review"],
            workers=["validator", "ai"],
            quality_gate=True,
        )

    execution_order = [task.task_id for task in tasks]
    notes: list[str] = [
        "NEXUS Manager decomposes the objective locally before calling any worker.",
        "Each task produces an artifact that can be passed to downstream workers.",
        "Workers are selected at execution time using capability, free-first status, and live readiness.",
    ]
    if analysis.needs_research and analysis.needs_presentation:
        notes.append("Research output is an input to presentation generation.")
    if analysis.needs_file_analysis and analysis.needs_presentation:
        notes.append("File analysis output is an input to presentation generation.")
    if analysis.needs_data_analysis and analysis.needs_presentation:
        notes.append("Analysis output is an input to presentation generation.")
    if add_quality_gate:
        notes.append("Manager QA is the terminal gate; PASS completes the mission and REWORK flags the mission for correction.")

    return TaskPlan(
        objective=analysis.objective,
        tasks=tasks,
        execution_order=execution_order,
        notes=notes,
    )
