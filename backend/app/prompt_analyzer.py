from __future__ import annotations

import re

from .prompt_models import IntentAnalysis


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def analyze_prompt(prompt: str) -> IntentAnalysis:
    """Deterministic first-pass prompt understanding."""
    text = " ".join(prompt.strip().lower().split())

    needs_research = _has_any(text, (
        "research", "competitor", "competitors", "market research", "market situation",
        "find information", "search", "sources", "literature", "benchmark", "investigate",
    ))
    needs_current = _has_any(text, (
        "latest", "current", "today", "recent", "live", "up-to-date", "up to date",
        "as of now", "current situation", "current market",
    ))
    needs_file = _has_any(text, (
        "excel", "xlsx", "csv", "spreadsheet", "attached file", "attachment", "dataset",
        "uploaded file", "pdf", "document",
    ))
    needs_presentation = _has_any(text, (
        "ppt", "pptx", "powerpoint", "presentation", "slides", "slide deck", "deck",
    ))
    needs_image = _has_any(text, (
        "image", "images", "infographic", "infographics", "diagram", "diagrams", "visual",
        "visuals", "illustration", "illustrations", "poster", "logo", "picture", "pictures",
        "graphic", "graphics", "chart", "flowchart", "mind map", "concept art", "draw",
        "sketch", "banner", "thumbnail",
    ))
    needs_code = _has_any(text, (
        "code", "coding", "program", "script", "website", "web app", "application", "debug",
        "api", "software", "function", "component", "repository", "repo",
    ))
    needs_data = _has_any(text, (
        "analyse", "analyze", "analysis", "data", "kpi", "metric", "metrics", "statistics",
        "calculate", "calculation", "model", "forecast", "trend", "regression", "dashboard",
    ))
    needs_writing = _has_any(text, (
        "write", "rewrite", "report", "essay", "summary", "summarize", "proposal", "email",
        "document", "memo", "case study", "content",
    ))
    needs_quality = _has_any(text, (
        "quality review", "quality check", "review the work", "review the final work",
        "review final work", "review the result", "review the output", "final review",
        "review before delivery", "review before final delivery", "before delivery",
        "validate the result", "validate the output", "validate the work", "check the result",
        "check the output", "check the work", "proofread", "audit the result", "audit the output",
        "verify the result", "verify the output", "quality assurance", "qa review",
    )) and not _has_any(text, (
        "don't review", "do not review", "skip review", "no quality check", "without review",
    ))

    if not needs_image and _has_word(text, ("create", "generate", "make", "design", "draw")) and _has_word(
        text, ("infographic", "diagram", "visual", "graphic", "illustration", "poster", "image")
    ):
        needs_image = True

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
    if _has_any(text, ("report", "document", "proposal", "memo", "case study")):
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
    if needs_image:
        requirements.append("make the visual output suitable for the requested purpose")
    if needs_quality:
        requirements.append("perform a quality review before final delivery")

    dependencies: list[str] = []
    if needs_research and needs_presentation:
        dependencies.append("research should feed presentation content")
    if needs_file and needs_presentation:
        dependencies.append("file analysis should feed presentation content")
    if needs_data and needs_presentation:
        dependencies.append("analysis should precede presentation generation")
    if needs_research and needs_data:
        dependencies.append("research should inform analytical interpretation")

    constraints: list[str] = []
    if _has_any(text, ("free", "no cost", "zero cost", "₹0", "without paying", "free ai")):
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

    objective = re.sub(r"\s+", " ", prompt.strip())

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
        needs_data_analysis=needs_data,
        needs_writing=needs_writing,
        needs_presentation=needs_presentation,
        needs_image=needs_image,
        needs_code=needs_code,
        needs_quality_review=needs_quality,
        confidence=confidence,
    )
