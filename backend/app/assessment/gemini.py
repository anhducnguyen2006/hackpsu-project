from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.api.schemas import (
    DataProfile,
    RelevanceAssessmentBatch,
    ResearchAssessment,
    ResearchInterpretation,
    UCIRecord,
)
from app.config import settings
from app.observability import get_request_id, timed_log

logger = logging.getLogger(__name__)

class GeminiUnavailableError(RuntimeError):
    """Raised when Gemini cannot be used for a request."""

    def __init__(
        self,
        message: str,
        *,
        category: str | None = None,
        model: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category or _failure_label(self)
        self.model = model
        self.original_exception_type = type(cause).__name__ if cause else None
        self.http_status = _http_status(cause) if cause else None
        self.cause_chain = _cause_chain(cause) if cause else []
        self.error_summary = _safe_error_summary(cause)


def _cause_chain(error: BaseException | None) -> list[str]:
    chain: list[str] = []
    current = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(type(current).__name__)
        current = current.__cause__ or current.__context__
    return chain


def _safe_error_summary(error: BaseException | None) -> str | None:
    if error is None:
        return None
    text = str(error).replace("\n", " ").strip()
    text = re.sub(r"(?:AIza|AQ\.)[A-Za-z0-9_-]+", "[redacted]", text)
    text = re.sub(r"([?&](?:key|token|api_key)=)[^&\s]+", r"\1[redacted]", text, flags=re.I)
    return text[:240] if text else type(error).__name__


def _http_status(error: BaseException | None) -> int | None:
    current = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for attribute in ("status_code", "status"):
            value = getattr(current, attribute, None)
            if isinstance(value, int) and 100 <= value <= 599:
                return value
        response = getattr(current, "response", None)
        value = getattr(response, "status_code", None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value
        details = getattr(current, "details", None)
        if isinstance(details, dict):
            value = details.get("code") or details.get("status_code")
            if isinstance(value, int) and 100 <= value <= 599:
                return value
        current = current.__cause__ or current.__context__
    return None


def _failure_label(error: Exception) -> str:
    text = str(error).lower()
    status = _http_status(error)
    if "429" in text or "resource_exhausted" in text or "quota" in text:
        return "quota/rate limit (not retried)"
    if "404" in text or "not found" in text or "not_found" in text:
        return "model unavailable"
    if status == 503 or "503" in text or "unavailable" in text:
        return "provider_http_503"
    if status == 504 or "504" in text or "deadline_exceeded" in text:
        return "provider_http_504"
    if isinstance(error, TimeoutError) or "timed out" in text or "timeout" in text:
        return "sdk_transport_timeout"
    if status is not None:
        return f"provider_http_{status}"
    return "request failure"


def _thinking_config(types: Any, model_name: str) -> Any | None:
    """Build thinking settings compatible with the configured Gemini family."""
    thinking_config_type = getattr(types, "ThinkingConfig", None)
    if thinking_config_type is None:
        return None
    normalized_model = model_name.lower().strip()
    if normalized_model.startswith(("gemini-3", "gemini-4")):
        thinking_levels = getattr(types, "ThinkingLevel", None)
        low = getattr(thinking_levels, "LOW", None) if thinking_levels else None
        return thinking_config_type(thinking_level=low) if low is not None else None
    if normalized_model in {"gemini-2.5-flash", "gemini-2.5-flash-lite"}:
        return thinking_config_type(thinking_budget=0)
    return None


def _interpret_thinking_config(types: Any, model_name: str) -> Any | None:
    """Build optional configurable thinking settings for interpretation only."""
    thinking_config_type = getattr(types, "ThinkingConfig", None)
    if thinking_config_type is None:
        return None
    if not model_name.lower().strip().startswith("gemini-3"):
        return None
    thinking_levels = getattr(types, "ThinkingLevel", None)
    if thinking_levels is None:
        return None
    configured_level = settings.gemini_interpret_thinking_level.strip().upper()
    level = getattr(thinking_levels, configured_level, None)
    return thinking_config_type(thinking_level=level) if level is not None else None


def _config(
    types: Any,
    schema: Any,
    *,
    max_output_tokens: int,
    model_name: str | None = None,
) -> Any:
    config = {
        "response_mime_type": "application/json",
        "response_schema": schema,
        "max_output_tokens": max_output_tokens,
    }
    thinking_config = _thinking_config(types, model_name or settings.gemini_model)
    if thinking_config is not None:
        config["thinking_config"] = thinking_config
    return types.GenerateContentConfig(**config)


def _interpret_config(types: Any, schema: Any, *, max_output_tokens: int) -> Any:
    config = {
        "response_mime_type": "application/json",
        "response_schema": schema,
        "max_output_tokens": max_output_tokens,
    }
    thinking_config = _interpret_thinking_config(types, settings.gemini_model)
    if thinking_config is not None:
        config["thinking_config"] = thinking_config
    return types.GenerateContentConfig(**config)


def _ensure_complete_response(response: Any, operation: str) -> None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return
    reason = getattr(candidates[0], "finish_reason", None)
    normalized = str(getattr(reason, "value", reason)).upper()
    if "MAX_TOKENS" in normalized or normalized in {"LENGTH", "RECITATION"}:
        raise ValueError(
            f"Gemini {operation} response was truncated ({normalized})."
        )


class GeminiService:
    # Bump whenever the suitability prompt or its expected interpretation changes.
    SUITABILITY_PROMPT_VERSION = "suitability-prompt-v2-compact-profile"

    def __init__(self, client: Any = None) -> None:
        self._client = client
        self.last_assessment_model: str | None = None
        self._interpretation_cache: dict[str, tuple[float, ResearchInterpretation]] = {}
        self.interpretation_cache_ttl_seconds = 300

    def interpret(self, research_question: str) -> ResearchInterpretation:
        if not settings.gemini_api_key and self._client is None:
            raise GeminiUnavailableError("GEMINI_API_KEY is not configured.")
        cache_key = " ".join(research_question.strip().split()).lower()
        cached = self._interpretation_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < self.interpretation_cache_ttl_seconds:
            logger.info("gemini operation=interpretation cache_hit=true")
            return cached[1]
        try:
            client = self._client or self._create_client()
            from google.genai import types

            prompt = (
                "Interpret this scientific research question for dataset discovery and "
                "return only the structured fields in the response schema. Preserve the "
                "researcher's original intent and do not narrow it without evidence. "
                "Rewrite unclear wording as one concise, searchable scientific question "
                "in refined_question; this is a suggestion, not a replacement. Identify "
                "independent and dependent variables only when applicable. For broad or "
                "exploratory questions, either list the applicable concepts or use empty "
                "lists rather than inventing a causal hypothesis. Identify population, "
                "geographic scope, and temporal scope only when supplied or reliably "
                "implied. Do not assume that an ambiguous term such as pollution means "
                "air pollution. Record important ambiguity or assumptions separately in "
                "assumptions_or_ambiguities. Include alternate scientific terminology and "
                "relevant synonyms. Generate 3 to 5 useful repository search terms. Never "
                "invent datasets, source names, dataset IDs, URLs, data availability, "
                "research findings, or statistics.\n\n"
                f"Research question: {research_question}"
            )
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=_interpret_config(
                    types, ResearchInterpretation, max_output_tokens=900
                ),
            )
            _ensure_complete_response(response, "interpretation")
            self._log_usage(response, "interpretation")
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                interpretation = ResearchInterpretation.model_validate(parsed)
            else:
                text = getattr(response, "text", None)
                if not text:
                    raise ValueError("Gemini returned an empty response.")
                interpretation = ResearchInterpretation.model_validate(json.loads(text))
            self._interpretation_cache[cache_key] = (time.monotonic(), interpretation)
            return interpretation
        except GeminiUnavailableError:
            raise
        except Exception as error:
            raise GeminiUnavailableError(
                f"Gemini interpretation failed ({_failure_label(error)}): {error}"
            ) from error

    def rerank(
        self,
        research_question: str,
        interpretation: ResearchInterpretation,
        candidates: list[UCIRecord],
    ) -> RelevanceAssessmentBatch:
        if not settings.gemini_api_key and self._client is None:
            raise GeminiUnavailableError("GEMINI_API_KEY is not configured.")
        candidate_payload = [
            {
                "dataset_id": candidate.dataset_id,
                "title": candidate.title,
                "description": candidate.description,
                "subject_area": candidate.subject_area,
                "variables": candidate.variables,
                "instance_count": candidate.instance_count,
                "feature_count": candidate.feature_count,
                "data_available": candidate.data_available,
            }
            for candidate in candidates[:12]
        ]
        prompt = (
            "Assess preliminary research relevance using ONLY the verified candidate "
            "metadata below. Return one assessment for candidate IDs that are relevant, "
            "partially relevant, or borderline; omit clearly irrelevant candidates. "
            "Never invent IDs, links, metadata, variables, statistics, or claims of "
            "causation. Prioritize outcome coverage, independent variable coverage, "
            "population match, topic match, and documented limitations. A score is a "
            "heuristic metadata-based relevance score, not a probability or suitability "
            "score. Every dataset_id must exactly match a supplied candidate ID.\n\n"
            f"Research question: {research_question}\n"
            f"Interpretation: {interpretation.model_dump_json()}\n"
            f"Verified candidates: {json.dumps(candidate_payload)}"
        )
        try:
            client = self._client or self._create_client()
            from google.genai import types

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=_config(
                    types, RelevanceAssessmentBatch, max_output_tokens=1400
                ),
            )
            _ensure_complete_response(response, "reranking")
            self._log_usage(response, "reranking")
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                return RelevanceAssessmentBatch.model_validate(parsed)
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Gemini returned an empty reranking response.")
            return RelevanceAssessmentBatch.model_validate(json.loads(text))
        except Exception as error:
            raise GeminiUnavailableError(
                f"Gemini reranking failed ({_failure_label(error)}): {error}"
            ) from error

    def assess_suitability(
        self,
        research_question: str,
        interpretation: ResearchInterpretation | None,
        dataset: UCIRecord,
        profile: DataProfile,
    ) -> ResearchAssessment:
        if not settings.gemini_api_key and self._client is None:
            raise GeminiUnavailableError("GEMINI_API_KEY is not configured.")
        primary_model = settings.gemini_model
        fallback_model = (settings.gemini_fallback_model or "").strip() or None
        models = [primary_model]
        if fallback_model and fallback_model != primary_model:
            models.append(fallback_model)
        overall_deadline = time.monotonic() + settings.gemini_overall_timeout_ms / 1000
        last_error: GeminiUnavailableError | None = None
        for index, model in enumerate(models):
            remaining_ms = max(1, int((overall_deadline - time.monotonic()) * 1000))
            if index and remaining_ms < settings.gemini_provider_min_timeout_ms:
                logger.warning(
                    "gemini fallback model=%s primary_model=%s outcome=skipped_remaining_deadline_ms=%s minimum_timeout_ms=%s",
                    model,
                    primary_model,
                    remaining_ms,
                    settings.gemini_provider_min_timeout_ms,
                )
                break
            if index == 0 and len(models) > 1:
                remaining_ms = min(
                    remaining_ms,
                    max(1, settings.gemini_overall_timeout_ms - settings.gemini_fallback_reserve_ms),
                )
            attempt_timeout_ms = min(settings.gemini_request_timeout_ms, remaining_ms)
            try:
                result = self._assess_suitability_once(
                    research_question,
                    interpretation,
                    dataset,
                    profile,
                    model,
                    attempt_timeout_ms,
                )
                if index:
                    logger.info(
                        "gemini fallback model=%s primary_model=%s outcome=success",
                        model,
                        primary_model,
                    )
                self.last_assessment_model = model
                return result
            except GeminiUnavailableError as error:
                last_error = error
                if index:
                    logger.warning(
                        "gemini fallback model=%s primary_model=%s outcome=failed category=%s",
                        model,
                        primary_model,
                        error.category,
                    )
                should_fallback = (
                    index == 0
                    and len(models) > 1
                    and error.category in {
                        "provider_http_503",
                        "provider_http_504",
                        "sdk_transport_timeout",
                    }
                    and time.monotonic() < overall_deadline
                )
                if not should_fallback:
                    raise
                logger.warning(
                    "gemini fallback model=%s primary_model=%s outcome=attempt_failed category=%s",
                    fallback_model,
                    primary_model,
                    error.category,
                )
        if last_error is not None:
            raise last_error
        raise GeminiUnavailableError("Gemini suitability assessment deadline expired.")

    def _assess_suitability_once(
        self,
        research_question: str,
        interpretation: ResearchInterpretation | None,
        dataset: UCIRecord,
        profile: DataProfile,
        model: str,
        timeout_ms: int,
    ) -> ResearchAssessment:
        prompt_started = time.perf_counter()
        evidence = {
            "question": research_question,
            "interpretation": interpretation.model_dump() if interpretation else None,
            "dataset_metadata": dataset.model_dump(mode="json"),
            "profile": self._compact_profile(profile),
        }
        prompt = (
            "Evaluate research suitability using ONLY the verified dataset metadata and "
            "deterministic profile below. Never invent variables, values, row counts, "
            "correlations, or statistics. Do not claim causation from observational data. "
            "Return all requested fields. Criteria scores are heuristic 0-100 values; "
            "use null when evidence is unavailable. Do not treat row count as independent "
            "participants, numeric encodings as exact units, or IDs as measurements. "
            "The final score will be recomputed by Python, so do not invent it.\n\n"
            f"Evidence: {json.dumps(evidence)}"
        )
        timed_log(
            logger,
            "gemini_prompt_construction",
            prompt_started,
            operation_type="suitability",
            model=model,
            timeout_ms=timeout_ms,
            prompt_characters=len(prompt),
            rows=profile.row_count,
            columns=profile.column_count,
        )
        generate_started: float | None = None
        generate_completed = False
        validation_started: float | None = None
        try:
            client = self._client or self._create_client(model_name=model, timeout_ms=timeout_ms)
            from google.genai import types

            generate_started = time.perf_counter()
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=_config(
                    types,
                    ResearchAssessment,
                    max_output_tokens=2200,
                    model_name=model,
                ),
            )
            timed_log(
                logger,
                "gemini_generate_content",
                generate_started,
                operation_type="suitability",
                model=model,
                timeout_ms=timeout_ms,
            )
            generate_completed = True
            validation_started = time.perf_counter()
            _ensure_complete_response(response, "suitability")
            self._log_usage(response, "suitability")
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                result = ResearchAssessment.model_validate(parsed)
                timed_log(logger, "gemini_response_validation", validation_started, operation_type="suitability", model=model)
                return result
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Gemini returned an empty suitability response.")
            result = ResearchAssessment.model_validate(json.loads(text))
            timed_log(logger, "gemini_response_validation", validation_started, operation_type="suitability", model=model)
            return result
        except Exception as error:
            if generate_started is not None and not generate_completed:
                timed_log(
                    logger,
                    "gemini_generate_content",
                    generate_started,
                    status=_failure_label(error),
                    operation_type="suitability",
                    model=model,
                    timeout_ms=timeout_ms,
                )
            timed_log(
                logger,
                "gemini_response_validation",
                validation_started if validation_started is not None else time.perf_counter(),
                status=_failure_label(error),
                operation_type="suitability",
                model=model,
                timeout_ms=timeout_ms,
                original_exception_type=type(error).__name__,
                http_status=_http_status(error),
                cause_chain=">".join(_cause_chain(error)),
                error_summary=_safe_error_summary(error),
            )
            raise GeminiUnavailableError(
                f"Gemini suitability assessment failed ({_failure_label(error)}): {error}",
                category=_failure_label(error),
                model=model,
                cause=error,
            ) from error

    @staticmethod
    def _compact_profile(profile: DataProfile) -> dict[str, Any]:
        """Keep verified research evidence while excluding redundant full-profile detail."""
        relevant_names = {
            name
            for evidence in profile.research_variable_evidence
            for name in evidence.matched_columns
        }
        relevant_names.update(
            column.name for column in profile.columns if column.research_roles
        )
        columns = []
        columns_to_send = (
            [column for column in profile.columns if column.name in relevant_names]
            if relevant_names
            else profile.columns
        )
        for column in columns_to_send:
            compact = {
                "name": column.name,
                "variable_description": column.variable_description,
                "data_type": column.data_type,
                "measurement_type": column.measurement_type,
                "missing_count": column.missing_count,
                "missing_fraction": column.missing_fraction,
                "unique_count": column.unique_count,
                "is_constant": column.is_constant,
                "is_near_empty": column.is_near_empty,
                "research_roles": column.research_roles,
            }
            if column.name in relevant_names:
                compact["numeric_summary"] = (
                    column.numeric_summary.model_dump(mode="json")
                    if column.numeric_summary is not None
                    else None
                )
                compact["categorical_summary"] = [
                    item.model_dump(mode="json") for item in column.categorical_summary
                ]
            columns.append(compact)
        return {
            "row_count": profile.row_count,
            "column_count": profile.column_count,
            "all_column_names": profile.column_names,
            "profiled_relevant_columns_only": bool(relevant_names),
            "duplicate_row_count": profile.duplicate_row_count,
            "columns": columns,
            "research_variable_evidence": [
                item.model_dump(mode="json") for item in profile.research_variable_evidence
            ],
            "correlations": [item.model_dump(mode="json") for item in profile.correlations],
            "quality_flags": profile.quality_flags,
        }

    def _create_client(self, *, model_name: str | None = None, timeout_ms: int | None = None) -> Any:
        try:
            from google import genai
            from google.genai import types
        except ImportError as error:
            raise GeminiUnavailableError(
                "The google-genai package is not installed."
            ) from error
        return genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=max(1, settings.gemini_retry_attempts),
                    initial_delay=1,
                    max_delay=4,
                    http_status_codes=[408, 500, 502, 503, 504],
                ),
                timeout=timeout_ms or settings.gemini_request_timeout_ms,
            ),
        )

    @staticmethod
    def _log_usage(response: Any, operation: str) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return
        logger.info(
            "gemini request_id=%s operation=%s prompt_tokens=%s output_tokens=%s total_tokens=%s",
            get_request_id(),
            operation,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            getattr(usage, "total_token_count", None),
        )
