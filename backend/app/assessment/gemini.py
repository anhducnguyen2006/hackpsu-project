from __future__ import annotations

import json
from typing import Any

from app.api.schemas import (
    RelevanceAssessmentBatch,
    ResearchInterpretation,
    UCIRecord,
)
from app.config import settings


class GeminiUnavailableError(RuntimeError):
    """Raised when Gemini cannot be used for a request."""


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
                ),
            )
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
            raise GeminiUnavailableError(f"Gemini interpretation failed: {error}") from error

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
            for candidate in candidates
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
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RelevanceAssessmentBatch,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                return RelevanceAssessmentBatch.model_validate(parsed)
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Gemini returned an empty reranking response.")
            return RelevanceAssessmentBatch.model_validate(json.loads(text))
        except Exception as error:
            raise GeminiUnavailableError(f"Gemini reranking failed: {error}") from error

    def _create_client(self) -> Any:
        try:
            from google import genai
        except ImportError as error:
            raise GeminiUnavailableError(
                "The google-genai package is not installed."
            ) from error
        return genai.Client(api_key=settings.gemini_api_key)
