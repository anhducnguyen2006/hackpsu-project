from __future__ import annotations

import hashlib
import json
import logging
import re
import time
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
)
from app.assessment.gemini import GeminiService
from app.assessment.suitability import calculate_final_score
from app.config import settings
from app.discovery.uci import UCIRepositoryError, UCIRepositoryService, dataset_record_from_uci
from app.discovery.search import DiscoveryService
from app.observability import timed_log
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
        self._cache: dict[tuple[str, str], DatasetAnalysisResponse] = {}
        self._data_cache: dict[int, tuple[object, object, object]] = {}
        self._data_cache_loaded_at: dict[int, float] = {}
        self._source_version_cache: dict[int, str] = {}
        self._profile_cache: dict[tuple[int, str, str], tuple[DataProfile, int | None]] = {}

    def analyze(self, dataset_id: str, request: AnalysisRequest) -> DatasetAnalysisResponse:
        total_started = time.perf_counter()
        key = (dataset_id, request.research_question.strip().lower())
        if key in self._cache:
            timed_log(logger, "analysis_request", total_started, status="memory_cache_hit", dataset_id=dataset_id)
            return self._cache[key]
        numeric_id = self._parse_id(dataset_id)
        metadata_started = time.perf_counter()
        metadata = self.repository.get_metadata(numeric_id)
        timed_log(logger, "uci_metadata_retrieval", metadata_started, dataset_id=numeric_id)
        warnings: list[str] = []
        interpretation = self._interpret(request.research_question, warnings)
        try:
            fetch_started = time.perf_counter()
            fetched = self._data_cache.get(numeric_id)
            if fetched is not None and (
                time.monotonic() - self._data_cache_loaded_at.get(numeric_id, 0)
                >= settings.uci_data_cache_ttl_seconds
            ):
                fetched = None
            if fetched is None:
                if isinstance(self.repository, UCIRepositoryService):
                    fetched = self.repository.fetch_dataset(
                        numeric_id, metadata_record=metadata
                    )
                else:
                    # Preserve compatibility with test and alternate repository
                    # adapters that expose the original one-argument method.
                    fetched = self.repository.fetch_dataset(numeric_id)
                self._data_cache[numeric_id] = fetched
                self._data_cache_loaded_at[numeric_id] = time.monotonic()
                self._source_version_cache.pop(numeric_id, None)
                fetch_status = "downloaded"
            else:
                fetch_status = "memory_cache_hit"
            timed_log(logger, "uci_dataset_fetch", fetch_started, status=fetch_status, dataset_id=numeric_id)
            source_record, dataframe, source_metadata = fetched
            source_version = self._source_version_cache.get(numeric_id)
            if source_version is None:
                source_started = time.perf_counter()
                source_version = self._source_version(dataframe, source_metadata)
                self._source_version_cache[numeric_id] = source_version
                timed_log(
                    logger,
                    "source_version_hash",
                    source_started,
                    dataset_id=numeric_id,
                    rows=len(dataframe),
                    columns=len(dataframe.columns),
                )
            profile, dataset_database_id = self._cached_or_profile(
                numeric_id,
                source_record,
                source_version,
                dataframe,
                interpretation,
                metadata.variable_descriptions,
                metadata.variable_types,
                warnings,
            )
        except Exception as error:
            response = DatasetAnalysisResponse(
                dataset=metadata,
                data_status="metadata_only",
                ai_assessment_status="unavailable",
                warnings=[f"Verified data could not be analyzed: {self._safe(error)}"],
            )
            timed_log(logger, "analysis_request", total_started, status="metadata_only", dataset_id=dataset_id)
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
        # Do not retain transient or unavailable AI results in the response cache.
        # A later request should be able to retry Gemini after provider recovery.
        if assessment is not None:
            self._cache[key] = response
        else:
            logger.info(
                "analysis_response_cache event=skip_unavailable dataset_id=%s",
                dataset_id,
            )
        timed_log(
            logger,
            "analysis_request",
            total_started,
            status="ok" if assessment else "assessment_unavailable",
            dataset_id=dataset_id,
            rows=profile.row_count,
            columns=profile.column_count,
        )
        return response

    def _cached_or_profile(
        self,
        numeric_id: int,
        source_record: object,
        source_version: str,
        dataframe: pd.DataFrame,
        interpretation: ResearchInterpretation | None,
        variable_descriptions: dict[str, str],
        variable_types: dict[str, str],
        warnings: list[str],
    ) -> tuple[DataProfile, int | None]:
        dataset_database_id: int | None = None
        profile_columns = self._profile_columns(
            dataframe,
            interpretation,
            variable_descriptions,
            variable_types,
        )
        profile_version = self.profiler.PROFILER_VERSION
        if profile_columns is not None:
            selection_digest = hashlib.sha256(
                json.dumps(profile_columns, separators=(",", ":")).encode("utf-8")
            ).hexdigest()[:12]
            profile_version = f"{profile_version}:{selection_digest}"
        profile_cache_key = (numeric_id, source_version, profile_version)
        cached_memory_profile = self._profile_cache.get(profile_cache_key)
        if cached_memory_profile is not None:
            timed_log(logger, "profile_cache", time.perf_counter(), status="memory_cache_hit", dataset_id=numeric_id)
            return cached_memory_profile
        cached_profile: dict[str, Any] | None = None
        cache_started = time.perf_counter()
        try:
            dataset_database_id = upsert_dataset(dataset_record_from_uci(source_record))
            cached_profile = get_dataset_profile(
                dataset_database_id,
                source_version,
                profile_version,
            )
            timed_log(
                logger,
                "profile_database_cache",
                cache_started,
                status="hit" if cached_profile is not None else "miss",
                dataset_id=numeric_id,
            )
        except Exception as error:
            timed_log(
                logger,
                "profile_database_cache",
                cache_started,
                status=type(error).__name__,
                dataset_id=numeric_id,
            )
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
                self._profile_cache[profile_cache_key] = (profile, dataset_database_id)
                return profile, dataset_database_id
            except Exception:
                logger.warning(
                    "dataset_profile_cache event=invalid dataset_id=%s",
                    numeric_id,
                )

        logger.info("dataset_profile_cache event=miss dataset_id=%s", numeric_id)
        profile_started = time.perf_counter()
        profile = self.profiler.profile(
            dataframe,
            interpretation,
            variable_descriptions,
            variable_types,
            profile_columns,
        )
        if profile_columns is not None:
            warnings.append(
                f"Wide dataset: profiled {len(profile.columns)} research-relevant "
                f"columns out of {len(dataframe.columns)} total columns."
            )
        timed_log(
            logger,
            "pandas_numpy_profiling",
            profile_started,
            dataset_id=numeric_id,
            rows=profile.row_count,
            columns=profile.column_count,
        )
        # Only a fully validated profile reaches persistence. Cache failures are
        # non-fatal because the current analysis result is still trustworthy.
        if dataset_database_id is not None:
            serialization_started = time.perf_counter()
            validated_profile = DataProfile.model_validate(profile)
            timed_log(
                logger,
                "data_profile_serialization",
                serialization_started,
                dataset_id=numeric_id,
                characters=len(validated_profile.model_dump_json()),
            )
            try:
                save_dataset_profile(
                    dataset_database_id,
                    source_version,
                    profile_version,
                    validated_profile,
                )
            except Exception:
                logger.warning(
                    "dataset_profile_cache event=save_failed dataset_id=%s",
                    numeric_id,
                )
                warnings.append(
                    "Persistent profile cache save failed; computed profile is available."
                )
        self._profile_cache[profile_cache_key] = (profile, dataset_database_id)
        return profile, dataset_database_id

    @staticmethod
    def _profile_columns(
        dataframe: pd.DataFrame,
        interpretation: ResearchInterpretation | None,
        variable_descriptions: dict[str, str],
        variable_types: dict[str, str],
    ) -> list[str] | None:
        """Select research-relevant columns only for unusually wide datasets."""
        if len(dataframe.columns) <= 500 or interpretation is None:
            return None
        terms = set(
            re.findall(
                r"[a-z0-9][a-z0-9-]{2,}",
                " ".join(
                    [
                        interpretation.research_subject,
                        *interpretation.independent_variables,
                        *interpretation.dependent_variables,
                        *interpretation.synonyms,
                        *interpretation.search_terms,
                    ]
                ).lower(),
            )
        )
        stop_words = {"the", "and", "with", "from", "for", "that", "this"}
        terms -= stop_words
        selected: list[str] = []
        for name in dataframe.columns:
            text = f"{name} {variable_descriptions.get(str(name), '')}".lower()
            column_terms = set(re.findall(r"[a-z0-9][a-z0-9-]{2,}", text))
            if terms & column_terms:
                selected.append(name)
        if not selected:
            selected = [
                name
                for name in dataframe.columns
                if variable_types.get(str(name), "").strip().lower()
                in {"binary", "categorical"}
                or not pd.api.types.is_numeric_dtype(dataframe[name])
            ][:50]
        return selected

    def _cached_or_assess(
        self,
        research_question: str,
        interpretation: ResearchInterpretation,
        dataset: Any,
        profile: DataProfile,
        source_version: str,
        dataset_database_id: int | None,
        warnings: list[str],
    ) -> ResearchAssessment:
        cache_key = self._assessment_cache_key(
            research_question,
            interpretation,
            dataset,
            profile,
            source_version,
        )
        if dataset_database_id is not None:
            cache_started = time.perf_counter()
            try:
                cached = get_cached_research_assessment(cache_key)
                if cached is not None:
                    assessment = ResearchAssessment.model_validate(cached)
                    logger.info(
                        "gemini_suitability_cache event=hit dataset_id=%s",
                        dataset.dataset_id,
                    )
                    timed_log(logger, "assessment_database_cache", cache_started, status="hit", dataset_id=dataset.dataset_id)
                    return assessment
            except Exception:
                timed_log(logger, "assessment_database_cache", cache_started, status="read_failed", dataset_id=dataset.dataset_id)
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
        score_started = time.perf_counter()
        assessment = calculate_final_score(ResearchAssessment.model_validate(generated))
        timed_log(logger, "calculate_final_score", score_started, dataset_id=dataset.dataset_id)
        if dataset_database_id is not None:
            save_started = time.perf_counter()
            try:
                save_research_assessment(
                    cache_key=cache_key,
                    dataset_id=dataset_database_id,
                    model=getattr(self.gemini, "last_assessment_model", None)
                    or settings.gemini_model,
                    assessment_version=GeminiService.SUITABILITY_PROMPT_VERSION,
                    assessment=assessment,
                )
                timed_log(
                    logger,
                    "assessment_database_save",
                    save_started,
                    dataset_id=dataset.dataset_id,
                    model=getattr(self.gemini, "last_assessment_model", None)
                    or settings.gemini_model,
                )
            except Exception:
                timed_log(logger, "assessment_database_save", save_started, status="save_failed", dataset_id=dataset.dataset_id)
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
    ) -> str:
        normalized_question = " ".join(research_question.strip().split()).lower()
        serialization_started = time.perf_counter()
        profile_payload = profile.model_dump(mode="json")
        timed_log(
            logger,
            "data_profile_serialization",
            serialization_started,
            dataset_id=dataset.dataset_id,
            characters=len(json.dumps(profile_payload, separators=(",", ":"))),
        )
        payload = {
            "normalized_research_question": normalized_question,
            "interpretation": interpretation.model_dump(mode="json"),
            "dataset_identity": {
                "dataset_id": dataset.dataset_id,
                "repository_url": str(dataset.repository_url),
            },
            "dataset_metadata": dataset.model_dump(mode="json"),
            "source_version": source_version,
            "profile_version": DataProfiler.PROFILER_VERSION,
            "profile": GeminiService._compact_profile(profile),
            "assessment_prompt_version": GeminiService.SUITABILITY_PROMPT_VERSION,
            "gemini_model": settings.gemini_model,
            "gemini_fallback_model": settings.gemini_fallback_model,
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
            warnings.append(
                f"Gemini interpretation unavailable; used deterministic fallback: "
                f"{self._safe(error)}"
            )
            return DiscoveryService._fallback_interpretation(question)

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
