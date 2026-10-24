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
    variable_descriptions: dict[str, str] = {}
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


class AnalysisRequest(BaseModel):
    research_question: str = Field(min_length=10, max_length=2000)


class NumericSummary(BaseModel):
    count: int
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = None
    minimum: float | None = None
    percentile_25: float | None = None
    percentile_75: float | None = None
    maximum: float | None = None


class CategoryCount(BaseModel):
    value: Any
    count: int


class ColumnProfile(BaseModel):
    name: str
    data_type: str
    measurement_type: Literal[
        "numeric",
        "ordinal_or_encoded_numeric",
        "categorical",
        "identifier_like",
    ]
    missing_count: int
    missing_fraction: float
    unique_count: int
    is_constant: bool
    is_near_empty: bool
    research_roles: list[Literal["independent", "outcome", "related"]] = []
    numeric_summary: NumericSummary | None = None
    categorical_summary: list[CategoryCount] = []


class CorrelationResult(BaseModel):
    column_a: str
    column_b: str
    pair_count: int
    pearson_correlation: float | None = None
    limitation: str


class ResearchVariableEvidence(BaseModel):
    research_variable: str
    matched_columns: list[str]
    usable_observations: int
    matched_pairs: dict[str, int] = {}
    notes: list[str] = []


class DataProfile(BaseModel):
    row_count: int
    column_count: int
    column_names: list[str]
    duplicate_row_count: int
    columns: list[ColumnProfile]
    research_variable_evidence: list[ResearchVariableEvidence] = []
    correlations: list[CorrelationResult] = []
    quality_flags: list[str] = []


class SuitabilityCriterion(BaseModel):
    score: int | None = Field(default=None, ge=0, le=100)
    explanation: str


class SuitabilityCriteria(BaseModel):
    research_question_and_outcome_alignment: SuitabilityCriterion
    required_variable_coverage: SuitabilityCriterion
    sample_size_considerations: SuitabilityCriterion
    data_quality_and_completeness: SuitabilityCriterion
    documentation_and_provenance: SuitabilityCriterion
    population_and_temporal_relevance: SuitabilityCriterion


class ResearchAssessment(BaseModel):
    dataset_summary: str
    relevant_independent_variables: list[str]
    relevant_outcome_variables: list[str]
    missing_or_unverified_research_variables: list[str]
    why_useful: list[str]
    statistical_methodological_strengths: list[str]
    data_quality_issues: list[str]
    population_limitations: list[str]
    sample_size_considerations: list[str]
    recommended_further_analyses: list[str]
    overall_assessment: str
    criteria: SuitabilityCriteria
    final_score: int | None = Field(default=None, ge=0, le=100)
    score_explanation: str
    ai_status: Literal["available", "unavailable"]


class DatasetAnalysisResponse(BaseModel):
    dataset: UCIRecord
    data_status: Literal["analyzed", "metadata_only", "failed"]
    profile: DataProfile | None = None
    assessment: ResearchAssessment | None = None
    ai_assessment_status: Literal["available", "unavailable"] = "unavailable"
    warnings: list[str] = []


class ExploreRequest(BaseModel):
    research_question: str = Field(min_length=10, max_length=2000)
    independent_variable: str = Field(min_length=1, max_length=200)
    outcome_variable: str = Field(min_length=1, max_length=200)


class ExploratoryCategory(BaseModel):
    category: Any
    observations: int
    mean_outcome: float | None = None
    median_outcome: float | None = None
    standard_deviation: float | None = None


class ExploratoryAnalysisResponse(BaseModel):
    dataset_id: str
    independent_variable: str
    outcome_variable: str
    independent_measurement_type: Literal["ordinal_or_encoded_numeric", "categorical"]
    outcome_measurement_type: Literal["numeric"]
    categories: list[ExploratoryCategory]
    missing_independent_count: int
    missing_outcome_count: int
    excluded_observation_count: int
    analyzed_observation_count: int
    limitations: list[str]
