from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

class GeminiUnavailableError(RuntimeError):
    """Raised when Gemini cannot be used for a request."""


def _failure_label(error: Exception) -> str:
    text = str(error).lower()
    if "429" in text or "resource_exhausted" in text or "quota" in text:
        return "quota/rate limit (not retried)"
    if "404" in text or "not found" in text or "not_found" in text:
        return "model unavailable"
    if "503" in text or "unavailable" in text:
        return "temporary service unavailability"
    if "504" in text or "deadline" in text or "timed out" in text or "timeout" in text:
        return "request timeout"
    return "request failure"


def _thinking_config(types: Any, model_name: str) -> Any | None:
    """Build thinking settings compatible with the configured Gemini family.

    Gemini 3+ uses ``thinking_level`` while older Gemini models reject that
    field. Keep this compatibility logic in one place so a model change in
    ``GEMINI_MODEL`` does not turn every structured request into a 400 error.
    """
    thinking_config_type = getattr(types, "ThinkingConfig", None)
    if thinking_config_type is None:
        return None
    normalized_model = model_name.lower().strip()
    if normalized_model.startswith(("gemini-3", "gemini-4")):
        thinking_levels = getattr(types, "ThinkingLevel", None)
        low = getattr(thinking_levels, "LOW", None) if thinking_levels else None
        return thinking_config_type(thinking_level=low) if low is not None else None
    if normalized_model in {"gemini-2.5-flash", "gemini-2.5-flash-lite"}:
        # These short extraction/ranking prompts do not need hidden reasoning.
        # A zero budget also avoids spending the response token cap on thoughts.
        return thinking_config_type(thinking_budget=0)
    return None


def _config(types: Any, schema: Any, *, max_output_tokens: int) -> Any:
    config = {
        "response_mime_type": "application/json",
        "response_schema": schema,
        "max_output_tokens": max_output_tokens,
    }
    thinking_config = _thinking_config(types, settings.gemini_model)
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
    SUITABILITY_PROMPT_VERSION = "suitability-prompt-v1"

    def __init__(self, client: Any = None) -> None:
        self._client = client
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
                config=_config(types, ResearchInterpretation, max_output_tokens=900),
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
        evidence = {
            "question": research_question,
            "interpretation": interpretation.model_dump() if interpretation else None,
            "dataset_metadata": dataset.model_dump(mode="json"),
            "profile": profile.model_dump(mode="json"),
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
        try:
            client = self._client or self._create_client()
            from google.genai import types

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=_config(types, ResearchAssessment, max_output_tokens=2200),
            )
            _ensure_complete_response(response, "suitability")
            self._log_usage(response, "suitability")
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                return ResearchAssessment.model_validate(parsed)
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Gemini returned an empty suitability response.")
            return ResearchAssessment.model_validate(json.loads(text))
        except Exception as error:
            raise GeminiUnavailableError(
                f"Gemini suitability assessment failed ({_failure_label(error)}): {error}"
            ) from error

    def _create_client(self) -> Any:
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
                    attempts=2,
                    initial_delay=1,
                    max_delay=4,
                    http_status_codes=[408, 500, 502, 503, 504],
                ),
                timeout=settings.gemini_request_timeout_ms,
            ),
        )

    @staticmethod
    def _log_usage(response: Any, operation: str) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return
        logger.info(
            "gemini operation=%s prompt_tokens=%s output_tokens=%s total_tokens=%s",
            operation,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
            getattr(usage, "total_token_count", None),
        )
