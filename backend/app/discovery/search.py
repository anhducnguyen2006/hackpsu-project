from __future__ import annotations

import re
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, Protocol

from app.api.schemas import (
    DatasetRecord,
    DatasetResult,
    RelevanceAssessment,
    ResearchInterpretation,
    UCIRecord,
)
from app.assessment.gemini import GeminiService
from app.config import settings
from app.discovery.dataverse import HarvardDataverseService
from app.discovery.embeddings import EmbeddingService, EmbeddingServiceError
from app.discovery.uci import dataset_record_from_uci
from app.discovery.zenodo import ZenodoService

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


class DiscoveryProvider(Protocol):
    source: str

    def search(self, search_terms: Iterable[str]) -> list[DatasetRecord]:
        ...


def build_external_providers() -> list[DiscoveryProvider]:
    providers: list[DiscoveryProvider] = []
    if settings.dataverse_enabled:
        providers.append(HarvardDataverseService())
    if settings.zenodo_enabled:
        providers.append(ZenodoService())
    return providers


class DiscoveryService:
    def __init__(
        self,
        repository,
        gemini: GeminiService,
        providers: Iterable[DiscoveryProvider] | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.repository = repository
        self.gemini = gemini
        self.providers = list(providers or [])
        self.embedding_service = embedding_service or EmbeddingService()
        self._cache: dict[tuple[str, int], tuple[float, tuple]] = {}
        self.cache_ttl_seconds = 300

    def search(
        self, question: str, limit: int
    ) -> tuple[ResearchInterpretation | None, list[DatasetResult], list[str], str]:
        return self.search_with_status(question, limit)[:4]

    def search_with_status(
        self, question: str, limit: int
    ) -> tuple[
        ResearchInterpretation | None,
        list[DatasetResult],
        list[str],
        str,
        str,
    ]:
        return self._search(question, limit)

    def _search(
        self, question: str, limit: int
    ) -> tuple[
        ResearchInterpretation | None,
        list[DatasetResult],
        list[str],
        str,
        str,
    ]:
        started = time.perf_counter()
        cache_key = (question.strip().lower(), limit)
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < self._cache_ttl(cached[1]):
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
        uci_records: list[UCIRecord] = []
        try:
            catalog = self.repository.discover_catalog()
        except Exception as error:
            warnings.append(f"UCI repository unavailable: {self._safe_error(error)}")
        else:
            logger.info("discovery stage=catalog elapsed_ms=%.1f records=%d", (time.perf_counter() - stage_started) * 1000, len(catalog))
            stage_started = time.perf_counter()
            candidates = self._rank_catalog(catalog, interpretation, 12)
            logger.info("discovery stage=filter elapsed_ms=%.1f candidates=%d", (time.perf_counter() - stage_started) * 1000, len(candidates))
            stage_started = time.perf_counter()
            uci_records = self._enrich(candidates, warnings)
            logger.info("discovery stage=enrichment elapsed_ms=%.1f enriched=%d", (time.perf_counter() - stage_started) * 1000, len(uci_records))

        stage_started = time.perf_counter()
        external_records = self._search_external(interpretation.search_terms, warnings)
        records = self._bound_records(
            self._deduplicate(
                [dataset_record_from_uci(record) for record in uci_records]
                + external_records
            ),
            settings.discovery_candidate_limit,
        )
        logger.info(
            "discovery stage=aggregation elapsed_ms=%.1f records=%d",
            (time.perf_counter() - stage_started) * 1000,
            len(records),
        )
        if not records:
            response = (
                interpretation,
                [],
                warnings,
                "keyword_fallback" if interpretation_failed else "partial_gemini",
                "keyword_fallback" if interpretation_failed else "unavailable",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            return response

        if interpretation_failed:
            results = self._fallback_results(records, interpretation)
            response = (
                interpretation,
                results[:limit],
                warnings,
                "keyword_fallback",
                "keyword_fallback",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            logger.info("discovery stage=response_keyword elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response

        try:
            stage_started = time.perf_counter()
            ranked = self.embedding_service.rank(
                question,
                records,
                settings.embedding_top_k,
            )
            results = [
                self._result_from_semantic_score(record, score)
                for record, score in ranked
            ]
            logger.info(
                "discovery stage=semantic_ranking elapsed_ms=%.1f candidates=%d",
                (time.perf_counter() - stage_started) * 1000,
                len(ranked),
            )
            response = (
                interpretation,
                results[:limit],
                warnings,
                "gemini",
                "semantic_embeddings",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            logger.info("discovery stage=response elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response
        except (EmbeddingServiceError, Exception) as error:
            warnings.append(
                f"Semantic embedding ranking unavailable; used metadata keyword fallback: "
                f"{self._safe_error(error)}"
            )
            response = (
                interpretation,
                self._fallback_results(records, interpretation)[:limit],
                warnings,
                "partial_gemini",
                "keyword_fallback",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            logger.info("discovery stage=response_fallback elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response

    def _search_external(
        self, search_terms: Iterable[str], warnings: list[str]
    ) -> list[DatasetRecord]:
        if not self.providers:
            return []
        records: list[DatasetRecord] = []
        workers = min(
            max(1, settings.discovery_source_concurrency), len(self.providers)
        )
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(provider.search, search_terms): provider
                for provider in self.providers
            }
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    records.extend(future.result())
                except Exception as error:
                    warnings.append(
                        f"{provider.source} unavailable: {self._safe_error(error)}"
                    )
        return records

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
    def _cache_ttl(response: tuple) -> int:
        return 300 if response[3] == "gemini" else 30

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
        records: list[DatasetRecord], interpretation: ResearchInterpretation
    ) -> list[DatasetResult]:
        results = []
        for record in records:
            terms = DiscoveryService._tokens(
                interpretation.dependent_variables
                + interpretation.independent_variables
                + interpretation.search_terms
            ) - GENERIC_TERMS
            text = DiscoveryService._record_tokens(record)
            matches = sorted(DiscoveryService._matching_terms(terms, text))
            if not matches:
                continue
            title_tokens = DiscoveryService._tokens([record.title])
            title_matches = DiscoveryService._matching_terms(set(matches), title_tokens)
            score = min(95, 35 + len(matches) * 10 + len(title_matches) * 15)
            results.append(
                DatasetResult(
                    **DiscoveryService._legacy_record(record).model_dump(),
                    source=record.source,
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
        record: DatasetRecord, assessment: RelevanceAssessment
    ) -> DatasetResult:
        explanation = assessment.relevance_explanation
        if "preliminary relevance" not in explanation.lower():
            explanation = (
                f"{explanation} This is preliminary metadata-based relevance, "
                "not research suitability."
            )
        return DatasetResult(
            **DiscoveryService._legacy_record(record).model_dump(),
            source=record.source,
            data_status="available" if record.data_available else "metadata_only",
            **assessment.model_copy(
                update={"relevance_explanation": explanation}
            ).model_dump(exclude={"dataset_id"}),
        )

    @staticmethod
    def _legacy_record(record: DatasetRecord) -> UCIRecord:
        if record.landing_page_url is None:
            raise ValueError(f"{record.id} has no verified landing page URL")
        descriptions = {
            variable.name: variable.description
            for variable in record.variables
            if variable.description
        }
        return UCIRecord(
            dataset_id=record.id,
            title=record.title,
            description=record.description,
            repository_url=record.landing_page_url,
            subject_area=record.subjects[0] if record.subjects else None,
            variables=[variable.name for variable in record.variables],
            variable_descriptions=descriptions,
            data_available=record.data_available,
        )

    @staticmethod
    def _record_tokens(record: DatasetRecord) -> set[str]:
        return DiscoveryService._tokens(
            [
                record.title,
                record.description or "",
                *[variable.name for variable in record.variables],
                *record.subjects,
            ]
        )

    @staticmethod
    def _deduplicate(records: list[DatasetRecord]) -> list[DatasetRecord]:
        seen: set[str] = set()
        unique: list[DatasetRecord] = []
        for record in records:
            key = DiscoveryService._dedupe_key(record)
            if key in seen:
                continue
            seen.add(key)
            unique.append(record)
        return unique

    @staticmethod
    def _dedupe_key(record: DatasetRecord) -> str:
        if record.doi:
            doi = record.doi.lower().strip()
            for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
                if doi.startswith(prefix):
                    doi = doi[len(prefix):]
            return f"doi:{doi}"
        return record.id.lower()

    @staticmethod
    def _bound_records(records: list[DatasetRecord], limit: int) -> list[DatasetRecord]:
        grouped: dict[str, list[DatasetRecord]] = {}
        for record in records:
            grouped.setdefault(record.source, []).append(record)
        bounded: list[DatasetRecord] = []
        while len(bounded) < limit and grouped:
            for source in list(grouped):
                record_list = grouped[source]
                if record_list:
                    bounded.append(record_list.pop(0))
                if not record_list:
                    del grouped[source]
                if len(bounded) >= limit:
                    break
        return bounded

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
