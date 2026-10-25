from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import pandas as pd

from app.api.schemas import (
    AnalysisRequest,
    DataProfile,
    DatasetAnalysisResponse,
    ExploreRequest,
    ExploratoryAnalysisResponse,
    ResearchInterpretation,
    ResearchAssessment,
    UCIRecord,
)
from app.assessment.gemini import GeminiService
from app.assessment.suitability import calculate_final_score
from app.config import settings
from app.discovery.uci import UCIRepositoryError, dataset_record_from_uci
from app.ingestion.guard import DownloadRejected
from app.ingestion.retrieve import SelectionError, load_table
from app.profiling.profiler import DataProfiler
from app.analysis.exploratory import ExploratoryAnalyzer
from app.research.repository import (
    get_cached_research_assessment,
    get_dataset_profile,
    save_research_assessment,
    save_dataset_profile,
    upsert_dataset,
)


logger = logging.getLogger(__name__)


class DatasetAnalysisService:
    def __init__(self, repository, gemini: GeminiService) -> None:
        self.repository = repository
        self.gemini = gemini
        self.profiler = DataProfiler()
        self.exploratory = ExploratoryAnalyzer()
        self._cache: dict[tuple[str, str, str], DatasetAnalysisResponse] = {}
        self._data_cache: dict[int, tuple[object, object, object]] = {}
        self._frames: dict[tuple[str, str], pd.DataFrame] = {}

    def analyze(
        self,
        dataset_id: str,
        request: AnalysisRequest,
        user_sub: str | None = None,
    ) -> DatasetAnalysisResponse:
        # The response cache includes the verified subject so one researcher's
        # assessment is not reused for another account. Dataset frames stay
        # shared because they are public source data, not private research.
        key = (user_sub or "", dataset_id, request.research_question.strip().lower())
        if key in self._cache:
            return self._cache[key]
        numeric_id = self._parse_id(dataset_id)
        metadata = self.repository.get_metadata(numeric_id)
        warnings: list[str] = []
        interpretation = self._interpret(request.research_question, warnings)
        try:
            fetched = self.repository.fetch_dataset(numeric_id)
            self._data_cache[numeric_id] = fetched
            source_record, dataframe, source_metadata = fetched
            source_version = self._source_version(dataframe, source_metadata)
            profile, dataset_database_id = self._cached_or_profile(
                numeric_id,
                source_record,
                source_version,
                dataframe,
                interpretation,
                metadata.variable_descriptions,
                warnings,
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
            assessment = self._cached_or_assess(
                request.research_question,
                interpretation,
                metadata,
                profile,
                source_version,
                dataset_database_id,
                warnings,
                user_sub,
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

    def analyze_selected(
        self,
        dataset_id: str,
        research_question: str,
        resource_id: str | None = None,
        user_sub: str | None = None,
    ) -> DatasetAnalysisResponse:
        """Analyze UCI natively or one re-resolved external file."""
        if dataset_id.startswith("uci:"):
            return self.analyze(
                dataset_id,
                AnalysisRequest(research_question=research_question),
                user_sub=user_sub,
            )
        key = (
            user_sub or "",
            dataset_id,
            resource_id or "",
            research_question.strip().lower(),
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        warnings: list[str] = []
        interpretation = self._interpret(research_question, warnings)
        try:
            record, resource, frame, inconclusive = load_table(dataset_id, resource_id)
        except (SelectionError, DownloadRejected) as error:
            raise
        except Exception as error:
            raise DownloadRejected(self._safe(error)) from error
        if inconclusive:
            warnings.append(
                "Provider type metadata was inconclusive. The file was parsed before it was marked download-verified."
            )
        resolved_id = resource.file_id or resource.filename or resource_id or ""
        self._frames[(dataset_id, resolved_id)] = frame
        if resource_id:
            self._frames[(dataset_id, resource_id)] = frame
        elif resolved_id:
            self._frames[(dataset_id, "")] = frame
        verified = record.model_copy(update={
            "title": record.title if record.title != "Pending provider metadata" else record.title,
            "eligibility_status": "download_verified",
            "eligibility_reason": (
                f"Parsed {resource.filename or resource.file_id} "
                f"({len(frame)} rows, {len(frame.columns)} columns) from the provider response."
            ),
            "download_performed": True,
            "download_resources": [resource],
            "data_available": True,
        })
        source_version = verified.source_version or resource.checksum or resolved_id
        profile, dataset_database_id = self._profile_record(
            verified, source_version, frame, interpretation, warnings
        )
        metadata = self._public_record(verified)
        assessment: ResearchAssessment | None = None
        try:
            if interpretation is None:
                raise RuntimeError("Research question interpretation was unavailable.")
            assessment = self._cached_or_assess(
                research_question,
                interpretation,
                metadata,
                profile,
                source_version,
                dataset_database_id,
                warnings,
                user_sub,
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
            analyzed_resource=resource,
            eligibility_status="download_verified",
            download_performed=True,
        )
        self._cache[key] = response
        return response

    def _profile_record(
        self,
        record,
        source_version: str,
        dataframe: pd.DataFrame,
        interpretation: ResearchInterpretation | None,
        warnings: list[str],
    ) -> tuple[DataProfile, int | None]:
        dataset_database_id: int | None = None
        cached_profile: dict[str, Any] | None = None
        try:
            dataset_database_id = upsert_dataset(record)
            cached_profile = get_dataset_profile(
                dataset_database_id,
                source_version,
                self.profiler.PROFILER_VERSION,
            )
        except Exception:
            warnings.append(
                "Persistent profile cache unavailable; computed profile was not cached."
            )
        if cached_profile is not None:
            try:
                return DataProfile.model_validate(cached_profile), dataset_database_id
            except Exception:
                warnings.append("Stored profile was invalid and was recomputed.")
        profile = self.profiler.profile(dataframe, interpretation, {})
        if dataset_database_id is not None:
            try:
                save_dataset_profile(
                    dataset_database_id,
                    source_version,
                    self.profiler.PROFILER_VERSION,
                    DataProfile.model_validate(profile),
                )
            except Exception:
                warnings.append(
                    "Persistent profile cache save failed; computed profile is available."
                )
        return profile, dataset_database_id

    @staticmethod
    def _public_record(record) -> UCIRecord:
        if record.landing_page_url is None:
            raise SelectionError(f"{record.id} has no landing page.")
        return UCIRecord(
            dataset_id=record.id,
            title=record.title,
            description=record.description,
            repository_url=record.landing_page_url,
            subject_area=record.subjects[0] if record.subjects else None,
            variables=[variable.name for variable in record.variables],
            data_available=True,
        )

    def _cached_or_profile(
        self,
        numeric_id: int,
        source_record: object,
        source_version: str,
        dataframe: pd.DataFrame,
        interpretation: ResearchInterpretation | None,
        variable_descriptions: dict[str, str],
        warnings: list[str],
    ) -> tuple[DataProfile, int | None]:
        dataset_database_id: int | None = None
        cached_profile: dict[str, Any] | None = None
        try:
            dataset_database_id = upsert_dataset(dataset_record_from_uci(source_record))
            cached_profile = get_dataset_profile(
                dataset_database_id,
                source_version,
                self.profiler.PROFILER_VERSION,
            )
        except Exception as error:
            logger.warning(
                "dataset_profile_cache event=unavailable dataset_id=%s",
                numeric_id,
            )
            warnings.append(
                "Persistent profile cache unavailable; computed profile was not cached."
            )

        if cached_profile is not None:
            try:
                profile = DataProfile.model_validate(cached_profile)
                logger.info(
                    "dataset_profile_cache event=hit dataset_id=%s",
                    numeric_id,
                )
                return profile, dataset_database_id
            except Exception:
                logger.warning(
                    "dataset_profile_cache event=invalid dataset_id=%s",
                    numeric_id,
                )

        logger.info("dataset_profile_cache event=miss dataset_id=%s", numeric_id)
        profile = self.profiler.profile(
            dataframe,
            interpretation,
            variable_descriptions,
        )
        # Only a fully validated profile reaches persistence. Cache failures are
        # non-fatal because the current analysis result is still trustworthy.
        if dataset_database_id is not None:
            try:
                save_dataset_profile(
                    dataset_database_id,
                    source_version,
                    self.profiler.PROFILER_VERSION,
                    DataProfile.model_validate(profile),
                )
            except Exception:
                logger.warning(
                    "dataset_profile_cache event=save_failed dataset_id=%s",
                    numeric_id,
                )
                warnings.append(
                    "Persistent profile cache save failed; computed profile is available."
                )
        return profile, dataset_database_id

    def _cached_or_assess(
        self,
        research_question: str,
        interpretation: ResearchInterpretation,
        dataset: Any,
        profile: DataProfile,
        source_version: str,
        dataset_database_id: int | None,
        warnings: list[str],
        user_sub: str | None = None,
    ) -> ResearchAssessment:
        cache_key = self._assessment_cache_key(
            research_question,
            interpretation,
            dataset,
            profile,
            source_version,
            user_sub,
        )
        if dataset_database_id is not None:
            try:
                cached = get_cached_research_assessment(cache_key)
                if cached is not None:
                    assessment = ResearchAssessment.model_validate(cached)
                    logger.info(
                        "gemini_suitability_cache event=hit dataset_id=%s",
                        dataset.dataset_id,
                    )
                    return assessment
            except Exception:
                logger.warning(
                    "gemini_suitability_cache event=read_failed dataset_id=%s",
                    dataset.dataset_id,
                )
                warnings.append(
                    "Persistent suitability cache unavailable; requested assessment was generated."
                )
        logger.info(
            "gemini_suitability_cache event=miss dataset_id=%s",
            dataset.dataset_id,
        )
        generated = self.gemini.assess_suitability(
            research_question, interpretation, dataset, profile
        )
        assessment = calculate_final_score(ResearchAssessment.model_validate(generated))
        if dataset_database_id is not None:
            try:
                save_research_assessment(
                    cache_key=cache_key,
                    dataset_id=dataset_database_id,
                    model=settings.gemini_model,
                    assessment_version=GeminiService.SUITABILITY_PROMPT_VERSION,
                    assessment=assessment,
                )
            except Exception:
                logger.warning(
                    "gemini_suitability_cache event=save_failed dataset_id=%s",
                    dataset.dataset_id,
                )
                warnings.append(
                    "Suitability assessment cache save failed; generated assessment is available."
                )
        return assessment

    @staticmethod
    def _assessment_cache_key(
        research_question: str,
        interpretation: ResearchInterpretation,
        dataset: Any,
        profile: DataProfile,
        source_version: str,
        user_sub: str | None = None,
    ) -> str:
        normalized_question = " ".join(research_question.strip().split()).lower()
        payload = {
            "owner_sub": user_sub or "",
            "normalized_research_question": normalized_question,
            "interpretation": interpretation.model_dump(mode="json"),
            "dataset_identity": {
                "dataset_id": dataset.dataset_id,
                "repository_url": str(dataset.repository_url),
            },
            "dataset_metadata": dataset.model_dump(mode="json"),
            "source_version": source_version,
            "profile_version": DataProfiler.PROFILER_VERSION,
            "profile": profile.model_dump(mode="json"),
            "assessment_prompt_version": GeminiService.SUITABILITY_PROMPT_VERSION,
            "gemini_model": settings.gemini_model,
            "gemini_configuration": {
                "response_schema": "ResearchAssessment",
                "response_mime_type": "application/json",
                "max_output_tokens": 2200,
                "request_timeout_ms": settings.gemini_request_timeout_ms,
            },
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _source_version(
        dataframe: pd.DataFrame, source_metadata: dict[str, Any]
    ) -> str:
        """Return a changing source revision, preferring provider revision fields.

        UCI does not currently expose a stable ETag or Last-Modified value through
        this adapter. The fallback is therefore a SHA-256 checksum of the fetched
        metadata, column schema, and dataframe contents rather than a permanent
        constant. A changed source dataset produces a different cache key.
        """
        for key in (
            "etag",
            "ETag",
            "last_modified",
            "Last-Modified",
            "revision",
            "version",
            "updated_at",
            "last_updated",
        ):
            value = source_metadata.get(key)
            if value is not None and str(value).strip():
                return f"{key}:{value}"

        digest = hashlib.sha256()
        digest.update(
            json.dumps(
                source_metadata,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        )
        digest.update(
            json.dumps(
                {"columns": [str(column) for column in dataframe.columns],
                 "dtypes": [str(dtype) for dtype in dataframe.dtypes]},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        try:
            digest.update(pd.util.hash_pandas_object(dataframe, index=True).values.tobytes())
        except (TypeError, ValueError):
            digest.update(dataframe.to_csv(index=True).encode("utf-8"))
        return f"sha256:{digest.hexdigest()}"

    def explore(
        self, dataset_id: str, request: ExploreRequest
    ) -> ExploratoryAnalysisResponse:
        if not dataset_id.startswith("uci:"):
            key = (dataset_id, request.resource_id or "")
            frame = self._frames.get(key)
            if frame is None:
                raise SelectionError(
                    "Analyze the selected file before requesting a grouped summary."
                )
            return self.exploratory.analyze(
                dataset_id,
                frame,
                request.independent_variable,
                request.outcome_variable,
            )
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
