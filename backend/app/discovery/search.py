from __future__ import annotations

import re
import logging
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
from app.discovery.eligibility import ELIGIBLE_STATUSES
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
        self._graph_records: dict[tuple[str, int], tuple[float, ResearchInterpretation | None, tuple[DatasetRecord, ...]]] = {}
        self.cache_ttl_seconds = 300

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
            candidates = self._expand_uci_candidates(catalog, candidates, interpretation)
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
        records = self._select_eligible(records, warnings)
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
            included = []
            for record, score in ranked:
                if score < settings.discovery_relevance_floor:
                    continue
                included.append((
                    record,
                    score,
                    self._concept_matches(record, concepts, score_rows),
                ))
            if ranked and not included:
                warnings.append(
                    "Eligible datasets were found, but none met the semantic relevance floor. "
                    "Weak matches were not added to fill the result limit."
                )
            included = included[:limit]
            results = [
                self._result_from_semantic_score(record, score, matches)
                for record, score, matches in included
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
                time.monotonic(), interpretation, tuple(record for record, _, _ in included)
            )
            logger.info("discovery stage=response elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response
        except Exception as error:
            warnings.append(
                f"Semantic embedding ranking unavailable; used metadata keyword fallback: "
                f"{self._safe_error(error)}"
            )
            fallback = self._fallback_results(records, interpretation)[:limit]
            fallback_ids = {item.dataset_id for item in fallback}
            response = (
                interpretation,
                fallback,
                warnings,
                "keyword_fallback" if interpretation_failed else "partial_gemini",
                "keyword_fallback",
            )
            self._cache[cache_key] = (time.monotonic(), response)
            self._graph_records[cache_key] = (
                time.monotonic(),
                interpretation,
                tuple(record for record in records if record.id in fallback_ids),
            )
            logger.info("discovery stage=response_fallback elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
            return response

    def _search_external(
        self, concepts: list[SearchConcept], warnings: list[str]
    ) -> list[DatasetRecord]:
        if not self.providers:
            return []
        queries = list(dict.fromkeys(concept.query for concept in concepts if concept.query))
        queries = queries[: max(1, settings.discovery_candidate_limit)]
        records: list[DatasetRecord] = []
        results_by_key: dict[tuple[str, str], list[DatasetRecord]] = {}
        workers = min(
            max(1, settings.discovery_source_concurrency),
            len(self.providers) * max(1, len(queries)),
        )
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(provider.search, [query]): (provider, query)
                for provider in self.providers
                for query in queries
            }
            for future in as_completed(futures):
                provider, query = futures[future]
                try:
                    results_by_key[(provider.source, query)] = list(future.result())
                except Exception as error:
                    results_by_key[(provider.source, query)] = []
                    warnings.append(
                        f"{provider.source} unavailable for query '{query}': {self._safe_error(error)}"
                    )
        # Query order is the concept order, not thread-completion order.
        cap = max(1, settings.discovery_candidate_limit)
        for provider in self.providers:
            combined: list[DatasetRecord] = []
            seen: set[str] = set()
            for query in queries:
                for record in results_by_key.get((provider.source, query), []):
                    if record.id in seen:
                        continue
                    seen.add(record.id)
                    combined.append(record)
            records.extend(combined[:cap])
        return records

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

    def _expand_uci_candidates(
        self,
        catalog: list[UCIRecord],
        lexical: list[UCIRecord],
        interpretation: ResearchInterpretation,
    ) -> list[UCIRecord]:
        """Let a bounded set of non-overlapping titles reach the embedding ranker.

        Lexical overlap remains the primary gate. Remaining slots are offered to
        catalog records that share no tokens, but only when the question embedding
        scores them at or above the relevance floor. This admits paraphrases
        without sending the whole catalog to metadata enrichment.
        """
        cap = 12
        if len(lexical) >= cap:
            return lexical[:cap]
        chosen = {record.dataset_id for record in lexical}
        extras = sorted(
            (record for record in catalog if record.dataset_id not in chosen),
            key=lambda record: record.dataset_id,
        )[: cap - len(lexical)]
        if not extras:
            return lexical
        try:
            adapted = [dataset_record_from_uci(record) for record in extras]
            scores = self.embedding_service.score_queries(
                [interpretation.original_research_question], adapted
            )
        except Exception:
            return lexical
        if not scores:
            return lexical
        expanded = list(lexical)
        for record, adapted_record in zip(extras, adapted):
            if scores[0].get(adapted_record.id, -1.0) >= settings.discovery_relevance_floor:
                expanded.append(record)
        return expanded[:cap]

    def _select_eligible(
        self, records: list[DatasetRecord], warnings: list[str]
    ) -> list[DatasetRecord]:
        selected: list[DatasetRecord] = []
        pending: list[DatasetRecord] = []
        for record in records:
            if record.source == "UCI Machine Learning Repository":
                marked = self._mark_uci(record)
                if marked is not None:
                    selected.append(marked)
                continue
            if record.eligibility_status in ELIGIBLE_STATUSES and any(
                resource.eligible for resource in record.download_resources
            ):
                selected.append(record)
                continue
            if record.eligibility_status == "unverified":
                pending.append(record)
        if pending:
            selected.extend(self._verify_pending(pending, warnings))
        selected.sort(key=lambda record: record.id)
        return selected

    def _verify_pending(
        self, pending: list[DatasetRecord], warnings: list[str]
    ) -> list[DatasetRecord]:
        providers = {provider.source: provider for provider in self.providers}

        def verify_one(record: DatasetRecord) -> DatasetRecord | None:
            verify = getattr(providers.get(record.source), "verify", None)
            if not callable(verify):
                return None
            verified = verify(record)
            if isinstance(verified, DatasetRecord) and verified.eligibility_status in ELIGIBLE_STATUSES:
                return verified
            return None

        verified: list[DatasetRecord] = []
        workers = min(max(1, settings.discovery_metadata_concurrency), len(pending))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(verify_one, record): record for record in pending}
            for future in as_completed(futures):
                record = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    warnings.append(
                        f"{record.source} metadata verification failed for {record.id}: "
                        f"{self._safe_error(error)}"
                    )
                    continue
                if result is not None:
                    verified.append(result)
        return verified

    @staticmethod
    def _mark_uci(record: DatasetRecord) -> DatasetRecord | None:
        if record.data_available is False:
            return None
        return record.model_copy(update={
            "eligibility_status": "supported_resource_verified",
            "eligibility_reason": (
                "UCI native retrieval path is available. Discovery did not download the table."
            ),
            "data_available": True,
            "download_performed": False,
        })

    @staticmethod
    def _data_status(record: DatasetRecord) -> str:
        if record.eligibility_status in ELIGIBLE_STATUSES:
            return "available"
        return "metadata_only"

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
                    data_status=DiscoveryService._data_status(record),
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
            data_status=DiscoveryService._data_status(record),
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
            data_status=DiscoveryService._data_status(record),
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
            "authors": record.authors,
            "publisher": record.publisher,
            "publication_date": record.publication_date,
            "keywords": record.keywords,
            "eligibility_status": record.eligibility_status,
            "eligibility_reason": record.eligibility_reason,
            "download_performed": record.download_performed,
            "source_version": record.source_version,
            "verification_candidates": record.verification_candidates,
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
        cleaned = question.strip()
        structured = DiscoveryService._parse_structured_fallback(cleaned)
        if structured is not None:
            independent, dependent, population, geographic, temporal, synonyms = structured
            phrase_terms = [
                term
                for term in (
                    independent,
                    dependent,
                    *synonyms,
                    *(population.split() if population else []),
                )
                if term
            ]
            terms = DiscoveryService._fallback_search_terms(phrase_terms, cleaned)
            subject_parts = [part for part in (independent, dependent) if part]
            return ResearchInterpretation(
                original_research_question=question,
                refined_question=None,
                research_subject=(
                    " and ".join(subject_parts) if subject_parts else "unspecified research topic"
                ),
                independent_variables=[independent] if independent else [],
                dependent_variables=[dependent] if dependent else [],
                target_population=population,
                population=population,
                geographic_scope=geographic,
                temporal_scope=temporal,
                synonyms=synonyms,
                search_terms=terms,
            )
        words = re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", cleaned.lower())
        fallback_stop_words = STOP_WORDS | {
            "datasets",
            "contain",
            "contains",
            "information",
            "about",
            "relate",
            "relates",
            "relationship",
            "between",
            "among",
        }
        meaningful = [word for word in words if word not in fallback_stop_words]
        meaningful = meaningful or words
        # Prefer keeping adjacent content words as phrases rather than splitting
        # an outcome like "sleep quality" across independent/dependent slots.
        joined = " ".join(meaningful)
        independent: list[str] = []
        dependent: list[str] = []
        if len(meaningful) >= 2:
            mid = max(1, len(meaningful) // 2)
            left = " ".join(meaningful[:mid]).strip()
            right = " ".join(meaningful[mid:]).strip()
            if left:
                independent = [left]
            if right:
                dependent = [right]
        elif meaningful:
            independent = [meaningful[0]]
        terms = DiscoveryService._fallback_search_terms(
            [*independent, *dependent], cleaned
        )
        return ResearchInterpretation(
            original_research_question=question,
            refined_question=None,
            research_subject=joined or "unspecified research topic",
            independent_variables=independent,
            dependent_variables=dependent,
            synonyms=[],
            search_terms=terms,
        )

    @staticmethod
    def _parse_structured_fallback(
        question: str,
    ) -> tuple[str, str, str | None, str | None, str | None, list[str]] | None:
        patterns = (
            r"(?:how\s+does|does)\s+(?P<independent>.+?)\s+affect\s+"
            r"(?P<dependent>.+?)(?:\s+(?:in|among|for)\s+(?P<population>[^?.!]+))?[?.!]?\s*$",
            r"(?:how\s+does|does)\s+(?P<independent>.+?)\s+relate(?:\s+to)?\s+"
            r"(?P<dependent>.+?)(?:\s+(?:in|among|for)\s+(?P<population>[^?.!]+))?[?.!]?\s*$",
            r"(?:effect|impact|influence)\s+of\s+(?P<independent>.+?)\s+on\s+"
            r"(?P<dependent>.+?)(?:\s+(?:in|among|for)\s+(?P<population>[^?.!]+))?[?.!]?\s*$",
            r"(?:relationship|association|link|correlation)\s+between\s+"
            r"(?P<independent>.+?)\s+and\s+(?P<dependent>.+?)"
            r"(?:\s+(?:in|among|for)\s+(?P<population>[^?.!]+))?[?.!]?\s*$",
            r"^(?P<independent>[^,?;]+?)\s+and\s+(?P<dependent>[^,?;]+?)[?.!]?\s*$",
        )
        for pattern in patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if not match:
                continue
            independent = match.group("independent").strip(" ,")
            dependent = match.group("dependent").strip(" ,")
            population_raw = ""
            if "population" in match.re.groupindex:
                population_raw = (match.group("population") or "").strip(" ,")
            if not independent or not dependent:
                continue
            if independent.lower() == dependent.lower():
                continue
            population, geographic, temporal = DiscoveryService._split_scope_hints(
                population_raw
            )
            synonyms = DiscoveryService._fallback_synonyms(independent, dependent)
            return independent, dependent, population, geographic, temporal, synonyms
        return None

    @staticmethod
    def _split_scope_hints(
        population_raw: str,
    ) -> tuple[str | None, str | None, str | None]:
        if not population_raw:
            return None, None, None
        text = population_raw.strip()
        temporal = None
        year_match = re.search(r"\b((?:19|20)\d{2})\b", text)
        if year_match:
            temporal = year_match.group(1)
            text = (text[: year_match.start()] + text[year_match.end() :]).strip(" ,")
        geographic = None
        geo_patterns = (
            (r"\bunited states\b|\bU\.?S\.?A?\.?\b|\bUS\b", "United States"),
            (r"\bunited kingdom\b|\bU\.?K\.?\b", "United Kingdom"),
            (r"\bcanada\b", "Canada"),
            (r"\bnepal\b", "Nepal"),
        )
        for pattern, label in geo_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                geographic = label
                text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
                break
        text = re.sub(r"\b(?:in|among|for|of)\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" ,")
        population = text or None
        return population, geographic, temporal

    @staticmethod
    def _fallback_synonyms(independent: str, dependent: str) -> list[str]:
        synonyms: list[str] = []
        independent_l = independent.lower()
        dependent_l = dependent.lower()
        if "caffeine" in independent_l:
            synonyms.extend(["caffeine consumption", "caffeine intake"])
        if "sleep quality" in dependent_l or dependent_l == "quality of sleep":
            synonyms.append("quality of sleep")
        if "rainfall" in independent_l or "precipitation" in independent_l:
            synonyms.append("precipitation")
        if "crop yield" in dependent_l:
            synonyms.append("agricultural yield")
        # Keep only distinct, non-identical paraphrases.
        return [
            item
            for item in dict.fromkeys(synonyms)
            if item.lower() not in {independent_l, dependent_l}
        ][:4]

    @staticmethod
    def _fallback_search_terms(phrases: list[str], question: str) -> list[str]:
        terms: list[str] = []
        for phrase in phrases:
            cleaned = phrase.strip().lower()
            if cleaned and cleaned not in terms:
                terms.append(cleaned)
            for token in re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", cleaned):
                if token not in STOP_WORDS and token not in terms:
                    terms.append(token)
            if len(terms) >= 5:
                break
        if len(terms) < 3:
            for token in re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", question.lower()):
                if token not in STOP_WORDS and token not in terms:
                    terms.append(token)
                if len(terms) >= 5:
                    break
        while len(terms) < 3:
            terms.append("research")
        return terms[:5]

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
