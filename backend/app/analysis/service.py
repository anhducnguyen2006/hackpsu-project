from __future__ import annotations

from app.api.schemas import (
    AnalysisRequest,
    DatasetResourceListing,
    DatasetAnalysisResponse,
    ExploreRequest,
    ExploratoryAnalysisResponse,
    ResearchInterpretation,
    ResearchAssessment,
    SourceAnalysisRequest,
    SourceDatasetAnalysisResponse,
)
from app.assessment.gemini import GeminiService
from app.assessment.suitability import calculate_final_score
from app.analysis.providers import (
    HarvardDataverseAnalysisProvider,
    ResourceProvider,
    ZenodoAnalysisProvider,
    provider_for_dataset,
)
from app.discovery.uci import UCIRepositoryError
from app.profiling.profiler import DataProfiler
from app.analysis.exploratory import ExploratoryAnalyzer


class DatasetAnalysisService:
    def __init__(
        self,
        repository,
        gemini: GeminiService,
        dataverse_provider: ResourceProvider | None = None,
        zenodo_provider: ResourceProvider | None = None,
    ) -> None:
        self.repository = repository
        self.gemini = gemini
        self.dataverse_provider = dataverse_provider or HarvardDataverseAnalysisProvider()
        self.zenodo_provider = zenodo_provider or ZenodoAnalysisProvider()
        self.profiler = DataProfiler()
        self.exploratory = ExploratoryAnalyzer()
        self._cache: dict[tuple[str, str], DatasetAnalysisResponse] = {}
        self._data_cache: dict[int, tuple[object, object, object]] = {}

    def list_resources(self, dataset_id: str) -> DatasetResourceListing:
        provider = provider_for_dataset(
            dataset_id,
            self.dataverse_provider,
            self.zenodo_provider,
        )
        return provider.list_resources(dataset_id)

    def analyze_source(
        self, request: SourceAnalysisRequest
    ) -> SourceDatasetAnalysisResponse:
        provider = provider_for_dataset(
            request.dataset_id,
            self.dataverse_provider,
            self.zenodo_provider,
        )
        dataset, resource, dataframe = provider.download(
            request.dataset_id, request.resource_id
        )
        warnings: list[str] = []
        interpretation = self._interpret(request.research_question, warnings)
        profile = self.profiler.profile(
            dataframe,
            interpretation,
            {
                variable.name: variable.description
                for variable in dataset.variables
                if variable.description
            },
        )
        assessment: ResearchAssessment | None = None
        try:
            if interpretation is None:
                raise RuntimeError("Research question interpretation was unavailable.")
            assessment = calculate_final_score(
                self.gemini.assess_suitability(
                    request.research_question, interpretation, dataset, profile
                )
            )
        except Exception as error:
            warnings.append(f"AI suitability assessment unavailable: {self._safe(error)}")
        return SourceDatasetAnalysisResponse(
            dataset=dataset,
            resource=resource.model_copy(update={"status": "analyzed"}),
            data_status="analyzed",
            profile=profile,
            assessment=assessment,
            ai_assessment_status="available" if assessment else "unavailable",
            warnings=warnings,
        )

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
