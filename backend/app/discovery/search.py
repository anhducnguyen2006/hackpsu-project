from __future__ import annotations

import re
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

from app.api.schemas import (
    DatasetResult,
    RelevanceAssessment,
    ResearchInterpretation,
    UCIRecord,
)
from app.assessment.gemini import GeminiService

logger = logging.getLogger(__name__)

GENERIC_TERMS = {
    "analysis", "attribute", "attributes", "data", "dataset", "health", "patient",
    "performance", "prediction", "predict", "study", "variable",
    "consumption", "quality", "effect", "affect",
}
STOP_WORDS = {
    "can", "does", "the", "and", "are", "between", "affect", "association",
    "with", "from", "for", "is", "there", "what", "relationship", "how",
}


class DiscoveryService:
    def __init__(self, repository, gemini: GeminiService) -> None:
        self.repository = repository
        self.gemini = gemini
        self._cache: dict[tuple[str, int], tuple[float, tuple]] = {}
        self.cache_ttl_seconds = 300

    def search(
        self, question: str, limit: int
    ) -> tuple[ResearchInterpretation | None, list[DatasetResult], list[str], str]:
        started = time.perf_counter()
        cache_key = (question.strip().lower(), limit)
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < self.cache_ttl_seconds:
            logger.info("discovery stage=cache_hit elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return cached[1]
        warnings: list[str] = []
        interpretation_failed = False
        stage_started = time.perf_counter()
        try:
            interpretation = self.gemini.interpret(question)
        except Exception as error:
            interpretation = self._fallback_interpretation(question)
            interpretation_failed = True
            warnings.append(
                f"Gemini unavailable; used metadata keyword fallback: {self._safe_error(error)}"
            )
        logger.info("discovery stage=interpretation elapsed_ms=%.1f", (time.perf_counter() - stage_started) * 1000)

        stage_started = time.perf_counter()
        try:
            catalog = self.repository.discover_catalog()
        except Exception as error:
            response = (
                interpretation,
                [],
                [f"UCI repository unavailable: {self._safe_error(error)}"],
                "keyword_fallback" if interpretation_failed else "partial_gemini",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            logger.info("discovery stage=response_repository_failure elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response
        logger.info("discovery stage=catalog elapsed_ms=%.1f records=%d", (time.perf_counter() - stage_started) * 1000, len(catalog))

        stage_started = time.perf_counter()
        candidates = self._rank_catalog(catalog, interpretation, 30)
        logger.info("discovery stage=filter elapsed_ms=%.1f candidates=%d", (time.perf_counter() - stage_started) * 1000, len(candidates))
        stage_started = time.perf_counter()
        enriched = self._enrich(candidates, warnings)
        logger.info("discovery stage=enrichment elapsed_ms=%.1f enriched=%d", (time.perf_counter() - stage_started) * 1000, len(enriched))
        if not enriched:
            response = (interpretation, [], warnings, "keyword_fallback" if interpretation_failed else "partial_gemini")
            self._cache[cache_key] = (time.monotonic(), response)
            return response

        if interpretation_failed:
            results = self._fallback_results(enriched, interpretation)
            response = (interpretation, results[:limit], warnings, "keyword_fallback")
            self._cache[cache_key] = (time.monotonic(), response)
            logger.info("discovery stage=response_keyword elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response

        try:
            stage_started = time.perf_counter()
            batch = self.gemini.rerank(question, interpretation, enriched)
            logger.info("discovery stage=reranking elapsed_ms=%.1f", (time.perf_counter() - stage_started) * 1000)
            candidate_ids = {candidate.dataset_id for candidate in enriched}
            assessments = {
                assessment.dataset_id: assessment
                for assessment in batch.assessments
                if assessment.dataset_id in candidate_ids
                and assessment.classification != "irrelevant"
            }
            results = [
                self._result_from_assessment(record, assessments[record.dataset_id])
                for record in enriched
                if record.dataset_id in assessments
            ]
            results.sort(
                key=lambda item: item.preliminary_relevance_score
                if item.preliminary_relevance_score is not None else -1,
                reverse=True,
            )
            response = (interpretation, results[:limit], warnings, "gemini")
            self._cache[cache_key] = (time.monotonic(), response)
            logger.info("discovery stage=response elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response
        except Exception as error:
            warnings.append(
                f"Gemini reranking unavailable; used metadata keyword fallback: "
                f"{self._safe_error(error)}"
            )
            response = (
                interpretation,
                self._fallback_results(enriched, interpretation)[:limit],
                warnings,
                "partial_gemini",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            logger.info("discovery stage=response_fallback elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response

    def _enrich(self, candidates: list[UCIRecord], warnings: list[str]) -> list[UCIRecord]:
        enriched = []
        def enrich_one(candidate: UCIRecord) -> UCIRecord:
            return self.repository.get_metadata(int(candidate.dataset_id.split(":")[1]))

        with ThreadPoolExecutor(max_workers=min(8, max(1, len(candidates)))) as executor:
            futures = {executor.submit(enrich_one, candidate): candidate for candidate in candidates}
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    enriched.append(future.result())
                except Exception as error:
                    warnings.append(
                        f"Could not enrich {candidate.dataset_id}: {self._safe_error(error)}"
                    )
        return enriched

    @staticmethod
    def _rank_catalog(
        catalog: list[UCIRecord], interpretation: ResearchInterpretation, count: int
    ) -> list[UCIRecord]:
        outcome_terms = DiscoveryService._tokens(
            interpretation.dependent_variables + interpretation.search_terms
        ) - GENERIC_TERMS
        variable_terms = DiscoveryService._tokens(
            interpretation.independent_variables + interpretation.synonyms
        ) - GENERIC_TERMS
        subject_terms = DiscoveryService._tokens(
            [interpretation.research_subject, interpretation.target_population or ""]
        ) - GENERIC_TERMS
        scored: list[tuple[int, UCIRecord]] = []
        for record in catalog:
            text = DiscoveryService._tokens(
                [record.title, record.description or "", *record.variables]
            )
            outcome_hits = len(DiscoveryService._matching_terms(outcome_terms, text))
            variable_hits = len(DiscoveryService._matching_terms(variable_terms, text))
            subject_hits = len(DiscoveryService._matching_terms(subject_terms, text))
            score = outcome_hits * 8 + variable_hits * 4 + subject_hits * 2
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].title))
        return [record for _, record in scored[:count]]

    @staticmethod
    def _fallback_results(
        records: list[UCIRecord], interpretation: ResearchInterpretation
    ) -> list[DatasetResult]:
        results = []
        for record in records:
            terms = DiscoveryService._tokens(
                interpretation.dependent_variables
                + interpretation.independent_variables
                + interpretation.search_terms
            ) - GENERIC_TERMS
            text = DiscoveryService._tokens(
                [record.title, record.description or "", *record.variables]
            )
            matches = sorted(DiscoveryService._matching_terms(terms, text))
            if not matches:
                continue
            title_tokens = DiscoveryService._tokens([record.title])
            title_matches = DiscoveryService._matching_terms(set(matches), title_tokens)
            score = min(95, 35 + len(matches) * 10 + len(title_matches) * 15)
            results.append(
                DatasetResult(
                    **record.model_dump(),
                    data_status="available" if record.data_available else "metadata_only",
                    preliminary_relevance_score=score,
                    relevance_explanation=(
                        f"Verified metadata matched: {', '.join(matches[:6])}. "
                        "This is keyword-ranked preliminary relevance, not research suitability."
                    ),
                    score_confidence="low",
                    matched_research_variables=matches,
                    missing_or_unverified_variables=[],
                    classification="partially_relevant",
                )
            )
        results.sort(
            key=lambda item: item.preliminary_relevance_score
            if item.preliminary_relevance_score is not None else -1,
            reverse=True,
        )
        return results

    @staticmethod
    def _result_from_assessment(
        record: UCIRecord, assessment: RelevanceAssessment
    ) -> DatasetResult:
        explanation = assessment.relevance_explanation
        if "preliminary relevance" not in explanation.lower():
            explanation = (
                f"{explanation} This is preliminary metadata-based relevance, "
                "not research suitability."
            )
        return DatasetResult(
            **record.model_dump(),
            data_status="available" if record.data_available else "metadata_only",
            **assessment.model_copy(
                update={"relevance_explanation": explanation}
            ).model_dump(exclude={"dataset_id"}),
        )

    @staticmethod
    def _fallback_interpretation(question: str) -> ResearchInterpretation:
        words = re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", question.lower())
        terms = list(dict.fromkeys(words))[:5]
        while len(terms) < 3:
            terms.append("research")
        return ResearchInterpretation(
            original_research_question=question,
            research_subject=" ".join(words[:4]) or "unspecified research topic",
            independent_variables=words[:2],
            dependent_variables=words[2:4],
            synonyms=[],
            search_terms=terms,
        )

    @staticmethod
    def _tokens(values: Iterable[str]) -> set[str]:
        return {
            token
            for value in values
            for token in re.findall(r"[a-z0-9]+", value.lower())
            if len(token) > 2
        }

    @staticmethod
    def _matching_terms(terms: set[str], text: set[str]) -> set[str]:
        return {
            term
            for term in terms
            if term not in STOP_WORDS
            and any(term == candidate or term in candidate or candidate in term for candidate in text)
        }

    @staticmethod
    def _safe_error(error: Exception) -> str:
        message = str(error)
        message = message.split("{", 1)[0].strip()
        message = re.sub(r"(AIza|AQ\.)[A-Za-z0-9_-]+", "[redacted]", message)
        return message[:300]
