from __future__ import annotations

import re
from threading import BoundedSemaphore

from app.api.schemas import (
    AnalysisProvenance,
    DatasetResourcesResponse,
    SourceAnalysisRequest,
    SourceAnalysisResponse,
)
from app.assessment.gemini import GeminiService
from app.assessment.suitability import calculate_final_score
from app.config import settings
from app.profiling.profiler import DataProfiler
from app.analysis.source_providers import (
    DataverseAnalysisProvider,
    SourceAnalysisProvider,
    SourceProviderError,
    UCIAnalysisProvider,
    ZenodoAnalysisProvider,
)


class SourceAnalysisService:
    """Coordinate safe resource selection, parsing, profiling, and assessment."""

    def __init__(
        self,
        providers: list[SourceAnalysisProvider] | None = None,
        gemini: GeminiService | None = None,
    ) -> None:
        self.providers = {provider.source: provider for provider in providers or []}
        self._providers_by_prefix = {
            "uci": next(
                (
                    provider
                    for provider in self.providers.values()
                    if provider.source == "UCI Machine Learning Repository"
                ),
                None,
            ),
            "dataverse": next(
                (provider for provider in self.providers.values() if provider.source == "Harvard Dataverse"),
                None,
            ),
            "zenodo": next(
                (provider for provider in self.providers.values() if provider.source == "Zenodo"),
                None,
            ),
        }
        self.gemini = gemini or GeminiService()
        self.profiler = DataProfiler()
        self._download_slots = BoundedSemaphore(max(1, settings.analysis_download_concurrency))

    def list_resources(self, dataset_id: str) -> DatasetResourcesResponse:
        provider = self._provider(dataset_id)
        dataset = provider.resolve(dataset_id)
        resources = provider.resources(dataset)
        eligible = [resource for resource in resources if resource.eligible]
        if not resources:
            status = "unsupported"
        elif not eligible:
            status = "unsupported"
        else:
            status = "compatible_tabular_available"
        return DatasetResourcesResponse(
            dataset=dataset,
            status=status,
            resources=eligible,
            warnings=(
                []
                if eligible
                else ["No public CSV or TSV resource is available for this dataset."]
            ),
        )

    def analyze(self, request: SourceAnalysisRequest) -> SourceAnalysisResponse:
        provider = self._provider(request.dataset_id)
        dataset = provider.resolve(request.dataset_id)
        resources = [resource for resource in provider.resources(dataset) if resource.eligible]
        base_provenance = AnalysisProvenance(
            provider=dataset.source,
            dataset_id=dataset.id,
            source_id=dataset.source_id,
            doi=dataset.doi,
            license=dataset.license,
            source_url=dataset.landing_page_url,
        )
        if not resources:
            return SourceAnalysisResponse(
                dataset=dataset,
                status="unsupported",
                completed_states=["metadata_found", "source_verified", "file_metadata_available"],
                provenance=base_provenance,
                warnings=["No public CSV or TSV resource is available for this dataset."],
            )
        selected = self._select_resource(resources, request.resource_id)
        if request.resource_id is not None and selected is None:
            raise ValueError("The selected resource does not belong to this dataset or is not eligible.")
        if selected is None:
            return SourceAnalysisResponse(
                dataset=dataset,
                status="compatible_tabular_available",
                completed_states=[
                    "metadata_found",
                    "source_verified",
                    "file_metadata_available",
                    "compatible_tabular_available",
                ],
                provenance=base_provenance,
                warnings=["Multiple eligible resources are available; select one explicitly."],
            )
        provenance = base_provenance.model_copy(
            update={
                "resource_id": selected.resource_id,
                "filename": selected.filename,
                "format": selected.format,
                "version": selected.version,
                "checksum": selected.checksum,
                "source_url": selected.source_url,
            }
        )
        states = [
            "metadata_found",
            "source_verified",
            "file_metadata_available",
            "compatible_tabular_available",
        ]
        try:
            with self._download_slots:
                dataframe = provider.download(dataset, selected)
            states.extend(["file_accessible", "file_downloaded", "file_parsed"])
            interpretation = self._interpret(request.research_question)
            profile = self.profiler.profile(dataframe, interpretation, self._descriptions(dataset))
            states.append("profile_available")
        except SourceProviderError as error:
            return SourceAnalysisResponse(
                dataset=dataset,
                resource=selected,
                status="unavailable",
                completed_states=states,
                provenance=provenance,
                warnings=[str(error)],
            )
        except Exception:
            return SourceAnalysisResponse(
                dataset=dataset,
                resource=selected,
                status="failed",
                completed_states=states,
                provenance=provenance,
                warnings=["The selected resource could not be analyzed safely."],
            )

        assessment = None
        warnings: list[str] = []
        try:
            if interpretation is None:
                raise RuntimeError("Research question interpretation was unavailable.")
            assessment = calculate_final_score(
                self.gemini.assess_suitability(
                    request.research_question,
                    interpretation,
                    dataset,
                    profile,
                )
            )
            states.append("assessment_available")
        except Exception:
            warnings.append("AI suitability assessment unavailable; deterministic profile preserved.")
        return SourceAnalysisResponse(
            dataset=dataset,
            resource=selected,
            status="assessment_available" if assessment else "profile_available",
            completed_states=states,
            profile=profile,
            assessment=assessment,
            ai_assessment_status="available" if assessment else "unavailable",
            provenance=provenance,
            warnings=warnings,
        )

    def _provider(self, dataset_id: str) -> SourceAnalysisProvider:
        match = re.fullmatch(r"([a-z][a-z0-9_-]*):(.*)", dataset_id.strip())
        if not match or not match.group(2):
            raise ValueError("Dataset ID must use a recognized source-prefixed format.")
        provider = self._providers_by_prefix.get(match.group(1))
        if provider is None:
            raise ValueError(
                "Source analysis supports uci:<id>, dataverse:<persistent-id>, and zenodo:<record-id>."
            )
        return provider

    @staticmethod
    def _select_resource(resources, resource_id: str | None):
        if resource_id is not None:
            return next((resource for resource in resources if resource.resource_id == resource_id), None)
        return resources[0] if len(resources) == 1 else None

    @staticmethod
    def _descriptions(dataset) -> dict[str, str]:
        return {
            variable.name: variable.description
            for variable in dataset.variables
            if variable.description
        }

    def _interpret(self, question: str):
        try:
            return self.gemini.interpret(question)
        except Exception:
            return None


def build_source_analysis_service() -> SourceAnalysisService:
    providers: list[SourceAnalysisProvider] = [UCIAnalysisProvider()]
    if settings.dataverse_enabled:
        providers.append(DataverseAnalysisProvider())
    if settings.zenodo_enabled:
        providers.append(ZenodoAnalysisProvider())
    return SourceAnalysisService(providers)
