from __future__ import annotations

import re

from .models import IntentAnalysis


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def analyze_prompt(prompt: str) -> IntentAnalysis:
    """Deterministic first-pass prompt understanding.

    This intentionally uses no external AI or network call. It gives NEXUS a
    stable contract that can later be validated or replaced by AI-assisted
    analysis without changing the API surface.
    """
    text = " ".join(prompt.strip().lower().split())

    needs_research = _has_any(text, ("research", "competitor", "market", "find information", "search", "sources", "literature"))
    needs_current = _has_any(text, ("latest", "current", "today", "recent", "live", "up-to-date", "as of now"))
    needs_file = _has_any(text, ("excel", "xlsx", "csv", "spreadsheet", "file", "pdf", "document", "attachment", "dataset"))
    needs_presentation = _has_any(text, ("ppt", "powerpoint", "presentation", "slides", "deck"))
    needs_image = _has_any(text, ("image", "diagram", "visual", "illustration", "poster", "logo", "picture"))
    needs_code = _has_any(text, ("code", "coding", "program", "script", "website", "app", "application", "debug", "api"))
    needs_data = _has_any(text, ("analyse", "analyze", "analysis", "data", "kpi", "metric", "statistics", "calculate", "model", "forecast"))
    needs_writing = _has_any(text, ("write", "rewrite", "report", "essay", "summary", "proposal", "email", "document"))
    needs_quality = not _has_any(text, ("don't review", "do not review", "skip review", "no quality check"))

    task_types: list[str] = []
    if needs_research:
        task_types.append("research")
    if needs_file:
        task_types.append("file_analysis")
    if needs_data:
        task_types.append("data_analysis")
    if needs_writing:
        task_types.append("writing")
    if needs_presentation:
        task_types.append("presentation")
    if needs_image:
        task_types.append("image_generation")
    if needs_code:
        task_types.append("coding")
    if needs_quality:
        task_types.append("quality_review")
    if not task_types:
        task_types.append("general_reasoning")

    deliverables: list[str] = []
    if needs_presentation:
        deliverables.append("presentation")
    if needs_image:
        deliverables.append("image")
    if needs_file and _has_any(text, ("excel", "xlsx", "spreadsheet")):
        deliverables.append("spreadsheet_analysis")
    if _has_any(text, ("report", "document", "proposal")):
        deliverables.append("written_document")
    if needs_code:
        deliverables.append("code")

    requirements: list[str] = []
    if needs_research:
        requirements.append("support research claims with appropriate sources")
    if needs_current:
        requirements.append("use current information where available")
    if needs_file:
        requirements.append("inspect supplied files before drawing conclusions")
    if needs_presentation:
        requirements.append("structure content for presentation use")
    if needs_data:
        requirements.append("show calculations or analytical basis for important conclusions")
    if needs_quality:
        requirements.append("perform a quality review before final delivery")

    dependencies: list[str] = []
    if needs_research and needs_presentation:
        dependencies.append("research should feed presentation content")
    if needs_file and needs_presentation:
        dependencies.append("file analysis should feed presentation content")
    if needs_data and needs_presentation:
        dependencies.append("analysis should precede presentation generation")

    constraints: list[str] = []
    if _has_any(text, ("free", "no cost", "zero cost", "₹0", "without paying")):
        constraints.append("use free resources only")
    if _has_any(text, ("quick", "quickly", "fast", "as soon as possible")):
        constraints.append("prioritize practical execution speed")

    confidence = 55.0
    detected = sum((needs_research, needs_file, needs_current, needs_presentation, needs_image, needs_code, needs_data, needs_writing))
    if detected >= 2:
        confidence += 15
    if len(task_types) >= 3:
        confidence += 10
    if len(prompt.strip()) >= 80:
        confidence += 10
    confidence = min(confidence, 90.0)

    objective = prompt.strip()
    objective = re.sub(r"\s+", " ", objective)

    return IntentAnalysis(
        objective=objective,
        task_types=task_types,
        deliverables=deliverables,
        requirements=requirements,
        dependencies=dependencies,
        constraints=constraints,
        needs_research=needs_research,
        needs_file_analysis=needs_file,
        needs_current_information=needs_current,
        needs_presentation=needs_presentation,
        needs_image=needs_image,
        needs_code=needs_code,
        needs_quality_review=needs_quality,
        confidence=confidence,
    )
