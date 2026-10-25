from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class DiscoveryRequest(BaseModel):
    research_question: str = Field(min_length=10, max_length=2000)
    limit: int = Field(default=8, ge=1, le=25)


class ResearchHistoryItem(BaseModel):
    id: int
    question: str
    normalized_question: str
    created_at: datetime


class SimilarResearchRequest(BaseModel):
    research_question: str = Field(min_length=1, max_length=2000)


class SimilarResearchItem(BaseModel):
    id: int
    question: str
    normalized_question: str
    created_at: datetime
    similarity_score: float


class ResearchSessionResponse(ResearchHistoryItem):
    datasets: list[dict[str, Any]] = Field(default_factory=list)
    assessments: list[dict[str, Any]] = Field(default_factory=list)


class ResearchInterpretation(BaseModel):
    original_research_question: str
    refined_question: str | None = None
    research_subject: str
    independent_variables: list[str]
    dependent_variables: list[str]
    # target_population is retained for API compatibility with existing clients.
    target_population: str | None = None
    population: str | None = None
    geographic_scope: str | None = None
    temporal_scope: str | None = None
    synonyms: list[str]
    assumptions_or_ambiguities: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def synchronize_population_fields(self) -> "ResearchInterpretation":
        if self.population is None:
            self.population = self.target_population
        if self.target_population is None:
            self.target_population = self.population
        return self


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


class DownloadResource(BaseModel):
    """A verified downloadable resource published by a dataset repository."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    format: str
    file_id: str | None = None
    filename: str | None = None
    original_filename: str | None = None
    content_type: str | None = None
    original_format: str | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    access_status: str | None = None
    eligible: bool = False

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("format")
    @classmethod
    def normalize_format(cls, value: str) -> str:
        normalized = value.strip().lower().lstrip(".")
        if not normalized:
            raise ValueError("format must not be empty")
        return normalized


class DatasetVariable(BaseModel):
    """Verified metadata for one published dataset variable."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    data_type: str | None = None
    unit: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("variable name must not be empty")
        return normalized

    @field_validator("description", "data_type", "unit", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class DatasetRecord(BaseModel):
    """Repository-neutral, provenance-preserving scientific dataset metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    source_id: str
    title: str
    description: str | None = None
    landing_page_url: HttpUrl | None = None
    download_resources: list[DownloadResource] = Field(default_factory=list)
    variables: list[DatasetVariable] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    geographic_coverage: list[str] = Field(default_factory=list)
    temporal_coverage: list[str] = Field(default_factory=list)
    doi: str | None = None
    license: str | None = None
    data_available: bool | None = None
    eligibility_status: Literal[
        "supported_resource_verified",
        "download_verified",
        "unsupported",
        "restricted",
        "verification_failed",
        "unverified",
    ] = "unverified"
    eligibility_reason: str | None = None
    download_performed: bool = False
    source_version: str | None = None
    verification_candidates: list[DownloadResource] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_stable_id(cls, value: str) -> str:
        normalized = value.strip()
        if ":" in normalized:
            prefix, suffix = normalized.split(":", 1)
            normalized = f"{prefix.lower()}:{suffix}"
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*:[^\s]+", normalized):
            raise ValueError(
                "id must be a stable source-prefixed identifier such as 'uci:320'"
            )
        return normalized

    @field_validator("source", "title")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("metadata text must not be empty")
        return normalized

    @field_validator("source_id")
    @classmethod
    def normalize_source_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or re.search(r"\s", normalized):
            raise ValueError(
                "source_id must be a non-empty identifier without spaces"
            )
        return normalized

    @field_validator(
        "description", "doi", "license", "landing_page_url", mode="before"
    )
    @classmethod
    def normalize_optional_metadata(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator(
        "subjects", "geographic_coverage", "temporal_coverage", mode="before"
    )
    @classmethod
    def normalize_text_lists(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                normalized.append(item)
                continue
            item = item.strip()
            if item and item not in normalized:
                normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def validate_source_id_suffix(self) -> "DatasetRecord":
        _, id_suffix = self.id.split(":", 1)
        if id_suffix != self.source_id:
            raise ValueError("id suffix must match source_id")
        return self


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


class ConceptMatch(BaseModel):
    """Verified evidence that a dataset matches one interpreted concept."""

    concept_id: str
    concept_type: Literal[
        "full_question",
        "independent_variable",
        "dependent_variable",
        "population_or_geography",
        "research_subject",
        "synonym",
        "search_term",
    ]
    concept: str
    matched_terms: list[str] = []
    matched_fields: list[str] = []
    evidence: list[str] = []
    semantic_similarity_score: float | None = Field(default=None, ge=-1, le=1)


class DatasetResult(UCIRecord):
    source: str = "UCI Machine Learning Repository"
    source_id: str | None = None
    landing_page_url: HttpUrl | None = None
    download_resources: list[DownloadResource] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    geographic_coverage: list[str] = Field(default_factory=list)
    temporal_coverage: list[str] = Field(default_factory=list)
    doi: str | None = None
    license: str | None = None
    eligibility_status: Literal[
        "supported_resource_verified",
        "download_verified",
        "unsupported",
        "restricted",
        "verification_failed",
        "unverified",
    ] = "unverified"
    eligibility_reason: str | None = None
    download_performed: bool = False
    source_version: str | None = None
    data_status: Literal["metadata_only", "available", "failed", "analyzed"]
    preliminary_relevance_score: int | None = Field(default=None, ge=0, le=100)
    semantic_similarity_score: float | None = Field(default=None, ge=-1, le=1)
    score_type: Literal["semantic_similarity", "keyword_fallback", "legacy_gemini"] = (
        "legacy_gemini"
    )
    concept_matches: list[ConceptMatch] = []
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
    ranking_status: Literal[
        "semantic_embeddings", "keyword_fallback", "unavailable", "demo_cached"
    ] = "unavailable"


class DiscoveryGraphRequest(BaseModel):
    research_question: str = Field(min_length=10, max_length=2000)
    limit: int = Field(default=8, ge=1, le=25)


class GraphNode(BaseModel):
    data: dict[str, Any]


class GraphEdge(BaseModel):
    data: dict[str, Any]


class KnowledgeGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class AnalysisRequest(BaseModel):
    research_question: str = Field(min_length=10, max_length=2000)


class DatasetResourceRequest(BaseModel):
    """Identifies a discovered dataset without putting slashes in the URL path."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=3, max_length=300)


class DatasetAnalysisCommand(BaseModel):
    """Analysis request for UCI and external datasets.

    ``resource_id`` is a provider file id or filename resolved by the server.
    Clients cannot submit a download URL.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=3, max_length=300)
    research_question: str = Field(min_length=10, max_length=2000)
    resource_id: str | None = Field(default=None, min_length=1, max_length=300)


class DatasetResourcesResponse(BaseModel):
    dataset_id: str
    provider: str
    source_version: str | None = None
    doi: str | None = None
    eligibility_status: Literal[
        "supported_resource_verified",
        "download_verified",
        "unsupported",
        "restricted",
        "verification_failed",
        "unverified",
    ] = "unverified"
    resources: list[DownloadResource] = Field(default_factory=list)
    verification_candidates: list[DownloadResource] = Field(default_factory=list)
    note: str | None = None


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
    analyzed_resource: DownloadResource | None = None
    eligibility_status: Literal[
        "supported_resource_verified",
        "download_verified",
        "unsupported",
        "restricted",
        "verification_failed",
        "unverified",
    ] | None = None
    download_performed: bool = False


class ExploreRequest(BaseModel):
    research_question: str = Field(min_length=10, max_length=2000)
    independent_variable: str = Field(min_length=1, max_length=200)
    outcome_variable: str = Field(min_length=1, max_length=200)
    resource_id: str | None = Field(default=None, min_length=1, max_length=300)


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
