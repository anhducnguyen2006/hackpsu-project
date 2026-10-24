from __future__ import annotations

import json
import logging
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


def _config(types: Any, schema: Any, *, max_output_tokens: int) -> Any:
    return types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        max_output_tokens=max_output_tokens,
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
    )


class GeminiService:
    def __init__(self, client: Any = None) -> None:
        self._client = client

    def interpret(self, research_question: str) -> ResearchInterpretation:
        if not settings.gemini_api_key and self._client is None:
            raise GeminiUnavailableError("GEMINI_API_KEY is not configured.")
        try:
            client = self._client or self._create_client()
            from google.genai import types

            prompt = (
                "Interpret this scientific research question for dataset discovery. "
                "Return only the requested structured fields. Generate research concepts "
                "and search terms, never dataset names, IDs, URLs, metadata, or statistics. "
                "Use 3 to 5 concise search terms.\n\n"
                f"Research question: {research_question}"
            )
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ResearchInterpretation,
                    max_output_tokens=700,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW
                    ),
                )
            )
            self._log_usage(response, "interpretation")
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                return ResearchInterpretation.model_validate(parsed)
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Gemini returned an empty response.")
            return ResearchInterpretation.model_validate(json.loads(text))
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
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ResearchAssessment,
                    max_output_tokens=2200,
                ),
            )
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
                    initialDelay=1,
                    maxDelay=4,
                    httpStatusCodes=[408, 500, 502, 503, 504],
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
