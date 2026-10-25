from app.api.schemas import ResearchInterpretation, UCIRecord
from app.discovery.search import DiscoveryService
from app.demo import demo_search


class FakeGemini:
    def interpret(self, question: str) -> ResearchInterpretation:
        return ResearchInterpretation(
            original_research_question=question,
            research_subject="student performance",
            independent_variables=["study time"],
            dependent_variables=["academic performance"],
            target_population="students",
            synonyms=["grades"],
            search_terms=["student", "studytime", "performance"],
        )


class FakeEmbedding:
    def score_queries(self, queries, candidates):
        return [
            {candidate.id: 0.9 - index * 0.01 for index, candidate in enumerate(candidates)}
            for _ in queries
        ]

    def rank(self, question, candidates, top_k):
        return [(candidate, 0.9 - index * 0.01) for index, candidate in enumerate(candidates[:top_k])]


class FakeRepository:
    def __init__(self) -> None:
        self.catalog_calls = 0

    def discover_catalog(self) -> list[UCIRecord]:
        self.catalog_calls += 1
        return [
            UCIRecord(
                dataset_id="uci:320",
                title="Student Performance",
                description="Student study time and performance",
                repository_url="https://archive.ics.uci.edu/dataset/320",
                variables=["studytime", "G3"],
            ),
            UCIRecord(
                dataset_id="uci:45",
                title="Heart Disease",
                description="Heart disease diagnosis",
                repository_url="https://archive.ics.uci.edu/dataset/45",
                variables=["age", "cholesterol"],
            ),
        ]

    def get_metadata(self, dataset_id: int) -> UCIRecord:
        return self.discover_catalog()[0]


def test_discovery_returns_only_repository_candidates() -> None:
    interpretation, datasets, warnings, mode = DiscoveryService(
        FakeRepository(), FakeGemini(), embedding_service=FakeEmbedding()
    ).search("Does study time affect grades?", 8)

    assert interpretation is not None
    assert [dataset.dataset_id for dataset in datasets] == ["uci:320"]
    assert datasets[0].semantic_similarity_score is not None
    assert datasets[0].score_type == "semantic_similarity"
    assert "not a probability" in datasets[0].relevance_explanation
    assert warnings == []
    assert mode == "keyword_fallback"


def test_normal_search_does_not_call_gemini_reranking() -> None:
    class NoRerankGemini(FakeGemini):
        def rerank(self, *args, **kwargs):
            raise AssertionError("Gemini reranking must not run in normal search")

    _, datasets, warnings, mode = DiscoveryService(
        FakeRepository(), NoRerankGemini(), embedding_service=FakeEmbedding()
    ).search("Does study time affect grades?", 8)

    assert datasets
    assert warnings == []
    assert mode == "keyword_fallback"


def test_gemini_failure_uses_labeled_fallback() -> None:
    class BrokenGemini:
        def interpret(self, question: str):
            raise RuntimeError("invalid API key")

    interpretation, datasets, warnings, mode = DiscoveryService(
        FakeRepository(), BrokenGemini(), embedding_service=FakeEmbedding()
    ).search("Does study time affect grades?", 8)

    assert datasets
    assert interpretation is not None
    assert interpretation.refined_question is None
    assert warnings == []
    assert mode == "keyword_fallback"


def test_fallback_interpretation_preserves_affect_and_geography_structure() -> None:
    interpretation = DiscoveryService._fallback_interpretation(
        "How does rainfall affect crop production in Nepal?"
    )

    assert interpretation.independent_variables == ["rainfall"]
    assert interpretation.dependent_variables == ["crop production"]
    assert interpretation.target_population == "Nepal"


def test_search_concepts_keep_original_and_refined_questions() -> None:
    interpretation = ResearchInterpretation(
        original_research_question="Does pollution affect health?",
        refined_question="What is the relationship between pollution exposure and health outcomes?",
        research_subject="pollution and health",
        independent_variables=["pollution exposure"],
        dependent_variables=["health outcomes"],
        synonyms=["environmental exposure"],
        search_terms=["pollution", "exposure", "health"],
    )
    concepts = DiscoveryService._build_concepts(interpretation)
    assert [concept.text for concept in concepts[:2]] == [
        interpretation.original_research_question,
        interpretation.refined_question,
    ]


def test_repository_failure_returns_empty_results() -> None:
    class BrokenRepository:
        def discover_catalog(self):
            raise RuntimeError("timeout")

    _, datasets, warnings, mode = DiscoveryService(
        BrokenRepository(), FakeGemini(), embedding_service=FakeEmbedding()
    ).search("Does study time affect grades?", 8)

    assert datasets == []
    assert any("UCI repository unavailable" in warning for warning in warnings)
    assert mode == "keyword_fallback"


def test_discovery_cache_avoids_repeating_repository_work() -> None:
    repository = FakeRepository()
    service = DiscoveryService(repository, FakeGemini(), embedding_service=FakeEmbedding())
    service.search("Does study time affect grades?", 8)
    first_call_count = repository.catalog_calls
    service.search("Does study time affect grades?", 8)
    assert repository.catalog_calls == first_call_count


def test_demo_search_is_labeled_and_does_not_match_unrelated_questions() -> None:
    _, datasets, warnings, _ = demo_search("Does study time affect academic performance?")
    assert datasets[0].dataset_id == "uci:320"
    assert datasets[1].dataset_id == "uci:856"
    assert datasets[1].instance_count == 145
    assert any("DEMO_MODE" in warning for warning in warnings)

    _, unrelated, warnings, _ = demo_search("What is quantum unicorn rainfall on Mars?")
    assert unrelated == []
    assert any("No cached demo result" in warning for warning in warnings)


def test_reranking_is_bounded_to_twelve_candidates() -> None:
    class CountingGemini(FakeGemini):
        def score_queries(self, queries, candidates):
            assert len(candidates) == 12
            return [{candidate.id: 0.5 for candidate in candidates} for _ in queries]

    records = [
        UCIRecord(
            dataset_id=f"uci:{index}",
            title=f"Student performance {index}",
            description="study grades student performance",
            repository_url=f"https://archive.ics.uci.edu/dataset/{index}",
            variables=["studytime", "G3"],
        )
        for index in range(1, 15)
    ]

    class ManyRepository(FakeRepository):
        def discover_catalog(self):
            return records

        def get_metadata(self, dataset_id: int):
            return records[dataset_id - 1]

    DiscoveryService(
        ManyRepository(), FakeGemini(), embedding_service=CountingGemini()
    ).search(
        "Does study time affect grades?", 8
    )
