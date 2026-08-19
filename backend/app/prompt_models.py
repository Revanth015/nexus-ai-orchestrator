from __future__ import annotations

from pydantic import BaseModel, Field


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)


class IntentAnalysis(BaseModel):
    objective: str
    task_types: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    needs_research: bool = False
    needs_file_analysis: bool = False
    needs_current_information: bool = False
    needs_data_analysis: bool = False
    needs_writing: bool = False
    needs_presentation: bool = False
    needs_image: bool = False
    needs_code: bool = False
    needs_quality_review: bool = True
    confidence: float = Field(ge=0, le=100)
    analyzer: str = "local_rules_v1"


class PromptAnalysisResponse(BaseModel):
    prompt: str
    analysis: IntentAnalysis
