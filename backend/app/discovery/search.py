from __future__ import annotations

import re
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable, Protocol

from app.api.schemas import (
    DatasetRecord,
    DatasetResult,
    ConceptMatch,
    RelevanceAssessment,
    ResearchInterpretation,
    UCIRecord,
)
from app.assessment.gemini import GeminiService
from app.config import settings
from app.discovery.dataverse import HarvardDataverseService
from app.discovery.embeddings import EmbeddingService
from app.discovery.uci import dataset_record_from_uci
from app.discovery.zenodo import ZenodoService
from app.graph.service import DatasetKnowledgeGraph

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


@dataclass(frozen=True)
class SearchConcept:
    concept_id: str
    concept_type: str
    text: str

    @property
    def query(self) -> str:
        return self.text.strip()


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
        self._external_cache: dict[tuple[str, str], tuple[float, tuple[DatasetRecord, ...]]] = {}
        self._external_cache_lock = threading.Lock()
        self._graph_records: dict[tuple[str, int], tuple[float, ResearchInterpretation | None, tuple[DatasetRecord, ...]]] = {}
        self.cache_ttl_seconds = 300
        self.external_cache_ttl_seconds = 120

    def graph_for_search(self, question: str, limit: int):
        """Return a graph for server-cached normalized records, populating the cache via search if needed."""
        cache_key = (question.strip().lower(), limit)
        cached = self._graph_records.get(cache_key)
        if not cached or time.monotonic() - cached[0] >= self.cache_ttl_seconds:
            self.search_with_status(question, limit)
            cached = self._graph_records.get(cache_key)
        if not cached:
            return DatasetKnowledgeGraph(
                max_datasets=settings.graph_candidate_limit,
                max_nodes=settings.graph_max_nodes,
                max_edges=settings.graph_max_edges,
            ).build([], None)
        _, interpretation, records = cached
        return DatasetKnowledgeGraph(
            max_datasets=settings.graph_candidate_limit,
            max_nodes=settings.graph_max_nodes,
            max_edges=settings.graph_max_edges,
        ).build(records, interpretation)

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
                f"Gemini unavailable; used deterministic interpretation fallback: "
                f"{self._safe_error(error)}"
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
        concepts = self._build_concepts(interpretation)
        external_records = self._search_external(concepts, warnings)
        records = self._deduplicate(
            [dataset_record_from_uci(record) for record in uci_records]
            + external_records
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
            self._graph_records[cache_key] = (time.monotonic(), interpretation, tuple())
            return response

        try:
            stage_started = time.perf_counter()
            score_rows = self._score_concepts(concepts, records)
            ranked = self._fuse_concept_scores(records, concepts, score_rows)
            results = [
                self._result_from_semantic_score(record, score, self._concept_matches(
                    record, concepts, score_rows
                ))
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
                "keyword_fallback" if interpretation_failed else "gemini",
                "semantic_embeddings",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            self._graph_records[cache_key] = (
                time.monotonic(), interpretation, tuple(record for record, _ in ranked[:limit])
            )
            logger.info("discovery stage=response elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response
        except Exception as error:
            warnings.append(
                f"Semantic embedding ranking unavailable; used metadata keyword fallback: "
                f"{self._safe_error(error)}"
            )
            response = (
                interpretation,
                self._fallback_results(records, interpretation)[:limit],
                warnings,
                "keyword_fallback" if interpretation_failed else "partial_gemini",
                "keyword_fallback",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            self._graph_records[cache_key] = (time.monotonic(), interpretation, tuple(records[:limit]))
            logger.info("discovery stage=response_fallback elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response

    def _search_external(
        self, concepts: list[SearchConcept], warnings: list[str]
    ) -> list[DatasetRecord]:
        if not self.providers:
            return []
        query = self._build_external_query(concepts)
        if not query:
            return []
        records: list[DatasetRecord] = []
        records_by_source: dict[str, list[DatasetRecord]] = {
            provider.source: [] for provider in self.providers
        }
        pending: list[DiscoveryProvider] = []
        for provider in self.providers:
            cache_key = (provider.source, query)
            with self._external_cache_lock:
                cached = self._external_cache.get(cache_key)
                if cached and time.monotonic() - cached[0] < self.external_cache_ttl_seconds:
                    records_by_source[provider.source].extend(cached[1])
                    continue
            pending.append(provider)

        if not pending:
            return self._external_records_by_source(records_by_source)

        workers = min(max(1, settings.discovery_source_concurrency), len(pending))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(provider.search, [query]): provider
                for provider in pending
            }
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    provider_records = tuple(future.result())
                    records_by_source[provider.source].extend(provider_records)
                    with self._external_cache_lock:
                        self._external_cache[(provider.source, query)] = (
                            time.monotonic(), provider_records
                        )
                except Exception as error:
                    warnings.append(
                        f"{provider.source} unavailable for query '{query}': {self._safe_error(error)}"
                    )
        return self._external_records_by_source(records_by_source)

    def _external_records_by_source(
        self, records_by_source: dict[str, list[DatasetRecord]]
    ) -> list[DatasetRecord]:
        records: list[DatasetRecord] = []
        for provider in self.providers:
            source_records = records_by_source[provider.source]
            source_limit = getattr(
                provider, "default_limit", settings.discovery_candidate_limit
            )
            records.extend(source_records[:source_limit])
        return records

    @classmethod
    def _build_external_query(cls, concepts: list[SearchConcept]) -> str:
        """Create one compact repository query from the interpreted concepts.

        External providers are supplemental sources. Sending every concept as a
        separate request multiplied latency by ``providers * concepts`` and made
        a slow provider dominate the request. One bounded query preserves the
        broad intent while keeping the fan-out to one request per provider.
        """
        preferred_types = {
            "search_term",
            "independent_variable",
            "dependent_variable",
            "research_subject",
            "population_or_geography",
        }
        tokens: list[str] = []
        seen: set[str] = set()
        for concept in concepts:
            if concept.concept_type not in preferred_types:
                continue
            for token in re.findall(r"[a-z0-9]+", concept.query.lower()):
                if len(token) <= 2 or token in STOP_WORDS or token in GENERIC_TERMS:
                    continue
                if token not in seen:
                    seen.add(token)
                    tokens.append(token)
                if len(tokens) >= 12:
                    return " ".join(tokens)
        return " ".join(tokens)

    @staticmethod
    def _build_concepts(interpretation: ResearchInterpretation) -> list[SearchConcept]:
        """Build bounded, deduplicated queries from the validated interpretation."""
        concepts: list[SearchConcept] = [
            SearchConcept("full_question", "full_question", interpretation.original_research_question),
        ]
        if interpretation.refined_question and interpretation.refined_question.strip():
            concepts.append(SearchConcept("refined_question", "full_question", interpretation.refined_question))
        if interpretation.research_subject.strip():
            concepts.append(SearchConcept("research_subject", "research_subject", interpretation.research_subject))
        for index, value in enumerate(interpretation.independent_variables):
            if value.strip():
                concepts.append(SearchConcept(f"independent_variable:{index}", "independent_variable", value))
        for index, value in enumerate(interpretation.dependent_variables):
            if value.strip():
                concepts.append(SearchConcept(f"dependent_variable:{index}", "dependent_variable", value))
        if interpretation.target_population and interpretation.target_population.strip():
            concepts.append(SearchConcept("population_or_geography", "population_or_geography", interpretation.target_population))
        if interpretation.synonyms:
            concepts.append(SearchConcept("synonyms", "synonym", " ".join(interpretation.synonyms)))
        for index, value in enumerate(interpretation.search_terms):
            if value.strip():
                concepts.append(SearchConcept(f"search_term:{index}", "search_term", value))
        unique: list[SearchConcept] = []
        seen_ids: set[str] = set()
        for concept in concepts:
            normalized = " ".join(concept.query.lower().split())
            if normalized and concept.concept_id not in seen_ids:
                seen_ids.add(concept.concept_id)
                unique.append(concept)
        return unique

    def _score_concepts(
        self, concepts: list[SearchConcept], records: list[DatasetRecord]
    ) -> list[dict[str, float]]:
        queries = [concept.query for concept in concepts]
        scorer = getattr(self.embedding_service, "score_queries", None)
        if callable(scorer):
            return scorer(queries, records)
        # Compatibility for injected ranking fakes and older embedding adapters.
        ranked = self.embedding_service.rank(
            concepts[0].query,
            records,
            len(records),
        )
        return [{record.id: score for record, score in ranked}] + [
            {} for _ in concepts[1:]
        ]

    @staticmethod
    def _fuse_concept_scores(
        records: list[DatasetRecord],
        concepts: list[SearchConcept],
        score_rows: list[dict[str, float]],
    ) -> list[tuple[DatasetRecord, float]]:
        """Fuse full-question and concept scores with renormalized group weights.

        Weights are full question=.45, independent variables=.25, dependent
        variables=.20, and context/subject/synonyms/search terms=.10. Missing
        groups are omitted and the remaining weights are renormalized, so a
        rainfall-only dataset is not discarded for lacking crop-yield metadata.
        """
        groups = {
            "full_question": (0.45, {"full_question"}),
            "independent_variable": (0.25, {"independent_variable"}),
            "dependent_variable": (0.20, {"dependent_variable"}),
            "context": (0.10, {"population_or_geography", "research_subject", "synonym", "search_term"}),
        }
        available = {name for name, (_, types) in groups.items() if any(
            concept.concept_type in types for concept in concepts
        )}
        weight_total = sum(groups[name][0] for name in available) or 1.0
        ranked: list[tuple[DatasetRecord, float]] = []
        for record in records:
            total = 0.0
            for name, (weight, types) in groups.items():
                values = [
                    score_rows[index].get(record.id)
                    for index, concept in enumerate(concepts)
                    if concept.concept_type in types and index < len(score_rows)
                ]
                values = [value for value in values if value is not None]
                if values:
                    total += (weight / weight_total) * max(values)
            ranked.append((record, float(total)))
        ranked.sort(key=lambda item: (-item[1], item[0].id))
        return ranked[: settings.embedding_top_k]

    @classmethod
    def _concept_matches(
        cls,
        record: DatasetRecord,
        concepts: list[SearchConcept],
        score_rows: list[dict[str, float]],
    ) -> list[ConceptMatch]:
        fields = {
            "title": cls._tokens([record.title]),
            "description": cls._tokens([record.description or ""]),
            "subjects": cls._tokens(record.subjects),
            "variables": cls._tokens(
                [variable.name for variable in record.variables]
                + [variable.description or "" for variable in record.variables]
            ),
            "geographic_coverage": cls._tokens(record.geographic_coverage),
            "temporal_coverage": cls._tokens(record.temporal_coverage),
        }
        matches: list[ConceptMatch] = []
        for index, concept in enumerate(concepts):
            terms = cls._tokens([concept.text]) - GENERIC_TERMS
            matched_fields = [
                field for field, text in fields.items()
                if cls._matching_terms(terms, text)
            ]
            matched_terms = sorted({
                term for field in matched_fields
                for term in cls._matching_terms(terms, fields[field])
            })
            score = score_rows[index].get(record.id) if index < len(score_rows) else None
            if not matched_terms and (score is None or score < 0.50):
                continue
            evidence = [
                f"Verified {field} metadata matched: {', '.join(matched_terms)}"
                for field in matched_fields
            ]
            if not evidence and score is not None:
                evidence = ["Semantic similarity to verified dataset metadata"]
            matches.append(ConceptMatch(
                concept_id=concept.concept_id,
                concept_type=concept.concept_type,
                concept=concept.text,
                matched_terms=matched_terms,
                matched_fields=matched_fields,
                evidence=evidence,
                semantic_similarity_score=score,
            ))
        return matches

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
                    **DiscoveryService._normalized_result_fields(record),
                    data_status="available" if record.data_available else "metadata_only",
                    preliminary_relevance_score=score,
                    relevance_explanation=(
                        f"Verified metadata matched: {', '.join(matches[:6])}. "
                        "This is keyword-ranked preliminary relevance, not research suitability."
                    ),
                    score_confidence="low",
                    score_type="keyword_fallback",
                    concept_matches=DiscoveryService._concept_matches(
                        record,
                        DiscoveryService._build_concepts(interpretation),
                        [],
                    ),
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
            **DiscoveryService._normalized_result_fields(record),
            data_status="available" if record.data_available else "metadata_only",
            **assessment.model_copy(
                update={"relevance_explanation": explanation}
            ).model_dump(exclude={"dataset_id"}),
        )

    @staticmethod
    def _result_from_semantic_score(
        record: DatasetRecord, score: float, concept_matches: list[ConceptMatch]
    ) -> DatasetResult:
        return DatasetResult(
            **DiscoveryService._legacy_record(record).model_dump(),
            source=record.source,
            **DiscoveryService._normalized_result_fields(record),
            data_status="available" if record.data_available else "metadata_only",
            semantic_similarity_score=score,
            score_type="semantic_similarity",
            concept_matches=concept_matches,
            relevance_explanation=(
                f"Semantic similarity: {score:.4f}. This score ranks verified metadata "
                "against the research question; it is not a probability, scientific "
                "suitability score, or evidence of causation."
            ),
            score_confidence="low",
            matched_research_variables=[],
            missing_or_unverified_variables=[],
            classification="partially_relevant",
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
    def _normalized_result_fields(record: DatasetRecord) -> dict:
        return {
            "source_id": record.source_id,
            "landing_page_url": record.landing_page_url,
            "download_resources": record.download_resources,
            "subjects": record.subjects,
            "geographic_coverage": record.geographic_coverage,
            "temporal_coverage": record.temporal_coverage,
            "doi": record.doi,
            "license": record.license,
        }

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
        structured = re.search(
            r"(?:how\s+does|does)\s+(?P<independent>.+?)\s+affect\s+"
            r"(?P<dependent>.+?)(?:\s+(?:in|among|for)\s+(?P<population>[^?.!]+))?[?.!]?$",
            question.strip(),
            re.IGNORECASE,
        )
        if structured:
            independent = structured.group("independent").strip(" ,")
            dependent = structured.group("dependent").strip(" ,")
            population = (structured.group("population") or "").strip(" ,") or None
            terms = list(dict.fromkeys(
                re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", " ".join(
                    part for part in (independent, dependent, population or "") if part
                ).lower())
            ))[:5]
            while len(terms) < 3:
                terms.append("research")
            return ResearchInterpretation(
                original_research_question=question,
                refined_question=None,
                research_subject=dependent or independent,
                independent_variables=[independent] if independent else [],
                dependent_variables=[dependent] if dependent else [],
                target_population=population,
                synonyms=[],
                search_terms=terms,
            )
        words = re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", question.lower())
        fallback_stop_words = STOP_WORDS | {
            "datasets",
            "contain",
            "contains",
            "information",
            "about",
        }
        meaningful = [word for word in words if word not in fallback_stop_words]
        meaningful = meaningful or words
        terms = list(dict.fromkeys(meaningful))[:5]
        while len(terms) < 3:
            terms.append("research")
        return ResearchInterpretation(
            original_research_question=question,
            refined_question=None,
            research_subject=" ".join(meaningful[:4]) or "unspecified research topic",
            independent_variables=meaningful[:2],
            dependent_variables=meaningful[2:4],
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
