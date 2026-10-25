from __future__ import annotations

from app.api.schemas import ResearchInterpretation, UCIRecord
from app.discovery.search import DiscoveryService


INTERPRETATION = ResearchInterpretation(
    original_research_question="How does rainfall affect crop production in Nepal?",
    research_subject="crop production",
    independent_variables=["rainfall"],
    dependent_variables=["crop production"],
    target_population="Nepal",
    synonyms=["precipitation", "crop yield"],
    search_terms=["rainfall", "crop production", "Nepal"],
)


def _record(dataset_id: str, title: str, description: str) -> UCIRecord:
    return UCIRecord(
        dataset_id=f"uci:{dataset_id}",
        title=title,
        description=description,
        repository_url=f"https://archive.ics.uci.edu/dataset/{dataset_id}",
        variables=["rainfall"] if "rainfall" in description.lower() else ["yield"],
    )


class Repository:
    records = [
        _record("1", "Rainfall observations", "Rainfall and precipitation measurements."),
        _record("2", "Crop yield production", "Agricultural crop production and yield."),
        _record("3", "Nepal rainfall crop production", "Rainfall and crop yield production in Nepal."),
        _record("4", "Nepal health survey", "Health outcomes and hospital observations in Nepal."),
    ]

    def discover_catalog(self):
        return self.records

    def get_metadata(self, dataset_id: int):
        return next(record for record in self.records if record.dataset_id == f"uci:{dataset_id}")


class Gemini:
    def interpret(self, question: str):
        return INTERPRETATION.model_copy(update={"original_research_question": question})


class ConceptEmbedding:
    seen_queries: list[str] = []

    def score_queries(self, queries, candidates):
        self.seen_queries.extend(queries)
        rows = []
        for query in queries:
            lowered = query.lower()
            row = {}
            for candidate in candidates:
                title = candidate.title.lower()
                if candidate.source_id == "3":
                    score = 0.95
                elif "rainfall" in lowered or "precipitation" in lowered:
                    score = 0.92 if candidate.source_id == "1" else 0.84 if candidate.source_id == "3" else 0.05
                elif "crop production" in lowered or "crop yield" in lowered:
                    score = 0.92 if candidate.source_id == "2" else 0.84 if candidate.source_id == "3" else 0.05
                elif "nepal" in lowered:
                    score = 0.88 if candidate.source_id in {"3", "4"} else 0.10
                elif "health" in title:
                    score = 0.02
                else:
                    score = 0.30
                row[candidate.id] = score
            rows.append(row)
        return rows


def search():
    embedding = ConceptEmbedding()
    response = DiscoveryService(Repository(), Gemini(), embedding_service=embedding).search(
        INTERPRETATION.original_research_question, 8
    )
    return response, embedding


def test_full_question_is_an_additional_semantic_query():
    (_, datasets, _, _), embedding = search()
    assert INTERPRETATION.original_research_question in embedding.seen_queries
    assert datasets[0].concept_matches
    assert any(match.concept_id == "full_question" for match in datasets[0].concept_matches)


def test_rainfall_only_dataset_is_retained_with_independent_match():
    (_, datasets, _, _), _ = search()
    rainfall = next(dataset for dataset in datasets if dataset.dataset_id == "uci:1")
    assert any(
        match.concept_type == "independent_variable" and "rainfall" in match.matched_terms
        for match in rainfall.concept_matches
    )


def test_crop_yield_only_dataset_is_retained_with_outcome_match():
    (_, datasets, _, _), _ = search()
    crop = next(dataset for dataset in datasets if dataset.dataset_id == "uci:2")
    assert any(
        match.concept_type == "dependent_variable" and match.matched_terms
        for match in crop.concept_matches
    )


def test_dataset_matching_both_concepts_ranks_above_unrelated_dataset():
    (_, datasets, _, _), _ = search()
    assert [dataset.dataset_id for dataset in datasets[:3]] == ["uci:3", "uci:1", "uci:2"]
    unrelated = next(dataset for dataset in datasets if dataset.dataset_id == "uci:4")
    assert unrelated.semantic_similarity_score < datasets[0].semantic_similarity_score


def test_missing_geographic_metadata_is_not_fabricated():
    (_, datasets, _, _), _ = search()
    rainfall = next(dataset for dataset in datasets if dataset.dataset_id == "uci:1")
    geo_matches = [
        match for match in rainfall.concept_matches
        if match.concept_type == "population_or_geography"
    ]
    assert all("nepal" not in match.matched_terms for match in geo_matches)
