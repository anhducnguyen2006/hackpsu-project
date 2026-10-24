from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class DiscoveryRequest(BaseModel):
    research_question: str = Field(min_length=10, max_length=2000)
    limit: int = Field(default=8, ge=1, le=25)


class ResearchInterpretation(BaseModel):
    original_research_question: str
    research_subject: str
    independent_variables: list[str]
    dependent_variables: list[str]
    target_population: str | None = None
    synonyms: list[str]
    search_terms: list[str] = Field(min_length=3, max_length=5)


class UCIRecord(BaseModel):
    dataset_id: str
    title: str
    description: str | None = None
    repository_url: HttpUrl
    subject_area: str | None = None
    variables: list[str] = []
    instance_count: int | None = None
    feature_count: int | None = None
    data_available: bool | None = None


class RelevanceAssessment(BaseModel):
    dataset_id: str
    preliminary_relevance_score: int | None = Field(default=None, ge=0, le=100)
    score_confidence: Literal["low", "medium", "high"]
    relevance_explanation: str
    matched_research_variables: list[str]
    missing_or_unverified_variables: list[str]
    classification: Literal["relevant", "partially_relevant", "irrelevant"]


class RelevanceAssessmentBatch(BaseModel):
    assessments: list[RelevanceAssessment]


class DatasetResult(UCIRecord):
    source: str = "UCI Machine Learning Repository"
    data_status: Literal["metadata_only", "available", "failed", "analyzed"]
    preliminary_relevance_score: int | None = Field(default=None, ge=0, le=100)
    relevance_explanation: str
    score_confidence: Literal["low", "medium", "high"] = "low"
    matched_research_variables: list[str] = []
    missing_or_unverified_variables: list[str] = []
    classification: Literal["relevant", "partially_relevant", "irrelevant"] = "partially_relevant"


class DiscoveryResponse(BaseModel):
    interpretation: ResearchInterpretation | None = None
    datasets: list[DatasetResult]
    explanation: str
    warnings: list[str] = []
    processing_mode: Literal["gemini", "partial_gemini", "keyword_fallback"]
