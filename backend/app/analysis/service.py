from __future__ import annotations

from app.api.schemas import (
    AnalysisRequest,
    DatasetAnalysisResponse,
    ExploreRequest,
    ExploratoryAnalysisResponse,
    ResearchInterpretation,
    ResearchAssessment,
)
from app.assessment.gemini import GeminiService
from app.assessment.suitability import calculate_final_score
from app.discovery.uci import UCIRepositoryError
from app.profiling.profiler import DataProfiler
from app.analysis.exploratory import ExploratoryAnalyzer


class DatasetAnalysisService:
    def __init__(self, repository, gemini: GeminiService) -> None:
        self.repository = repository
        self.gemini = gemini
        self.profiler = DataProfiler()
        self.exploratory = ExploratoryAnalyzer()
        self._cache: dict[tuple[str, str], DatasetAnalysisResponse] = {}
        self._data_cache: dict[int, tuple[object, object, object]] = {}

    def analyze(self, dataset_id: str, request: AnalysisRequest) -> DatasetAnalysisResponse:
        key = (dataset_id, request.research_question.strip().lower())
        if key in self._cache:
            return self._cache[key]
        numeric_id = self._parse_id(dataset_id)
        metadata = self.repository.get_metadata(numeric_id)
        warnings: list[str] = []
        interpretation = self._interpret(request.research_question, warnings)
        try:
            fetched = self.repository.fetch_dataset(numeric_id)
            self._data_cache[numeric_id] = fetched
            _, dataframe, _ = fetched
            profile = self.profiler.profile(
                dataframe,
                interpretation,
                metadata.variable_descriptions,
            )
        except Exception as error:
            response = DatasetAnalysisResponse(
                dataset=metadata,
                data_status="metadata_only",
                ai_assessment_status="unavailable",
                warnings=[f"Verified data could not be analyzed: {self._safe(error)}"],
            )
            self._cache[key] = response
            return response

        assessment: ResearchAssessment | None = None
        try:
            if interpretation is None:
                raise RuntimeError("Research question interpretation was unavailable.")
            assessment = calculate_final_score(
                self.gemini.assess_suitability(
                    request.research_question, interpretation, metadata, profile
                )
            )
        except Exception as error:
            warnings.append(f"AI suitability assessment unavailable: {self._safe(error)}")
        response = DatasetAnalysisResponse(
            dataset=metadata,
            data_status="analyzed",
            profile=profile,
            assessment=assessment,
            ai_assessment_status="available" if assessment else "unavailable",
            warnings=warnings,
        )
        self._cache[key] = response
        return response

    def explore(
        self, dataset_id: str, request: ExploreRequest
    ) -> ExploratoryAnalysisResponse:
        numeric_id = self._parse_id(dataset_id)
        if numeric_id not in self._data_cache:
            self._data_cache[numeric_id] = self.repository.fetch_dataset(numeric_id)
        _, dataframe, _ = self._data_cache[numeric_id]
        return self.exploratory.analyze(
            dataset_id,
            dataframe,
            request.independent_variable,
            request.outcome_variable,
        )

    def _interpret(
        self, question: str, warnings: list[str]
    ) -> ResearchInterpretation | None:
        try:
            return self.gemini.interpret(question)
        except Exception as error:
            warnings.append(f"AI interpretation unavailable: {self._safe(error)}")
            return None

    @staticmethod
    def _parse_id(dataset_id: str) -> int:
        if not dataset_id.startswith("uci:"):
            raise ValueError("Dataset ID must use the verified uci:<integer> format.")
        try:
            value = int(dataset_id[4:])
        except ValueError as error:
            raise ValueError("Dataset ID must use the verified uci:<integer> format.") from error
        if value <= 0:
            raise ValueError("Dataset ID must be positive.")
        return value

    @staticmethod
    def _safe(error: Exception) -> str:
        import re

        return re.sub(r"(AIza|AQ\.)[A-Za-z0-9_-]+", "[redacted]", str(error))
