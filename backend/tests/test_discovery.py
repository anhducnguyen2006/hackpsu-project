from app.api.schemas import RelevanceAssessmentBatch, ResearchInterpretation, UCIRecord
from app.discovery.search import DiscoveryService


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

    def rerank(self, question, interpretation, candidates):
        return RelevanceAssessmentBatch(
            assessments=[
                {
                    "dataset_id": "uci:320",
                    "preliminary_relevance_score": 92,
                    "score_confidence": "high",
                    "relevance_explanation": "Verified outcome and variable metadata match.",
                    "matched_research_variables": ["studytime", "G3"],
                    "missing_or_unverified_variables": ["causal effect"],
                    "classification": "relevant",
                },
                {
                    "dataset_id": "uci:999",
                    "preliminary_relevance_score": 99,
                    "score_confidence": "high",
                    "relevance_explanation": "This ID is not a supplied candidate.",
                    "matched_research_variables": [],
                    "missing_or_unverified_variables": [],
                    "classification": "relevant",
                },
            ]
        )


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
        FakeRepository(), FakeGemini()
    ).search("Does study time affect grades?", 8)

    assert interpretation is not None
    assert [dataset.dataset_id for dataset in datasets] == ["uci:320"]
    assert datasets[0].preliminary_relevance_score is not None
    assert "preliminary" in datasets[0].relevance_explanation
    assert warnings == []
    assert mode == "gemini"


def test_gemini_failure_uses_labeled_fallback() -> None:
    class BrokenGemini:
        def interpret(self, question: str):
            raise RuntimeError("invalid API key")

    _, datasets, warnings, mode = DiscoveryService(
        FakeRepository(), BrokenGemini()
    ).search("Does study time affect grades?", 8)

    assert datasets
    assert warnings
    assert "Gemini unavailable" in warnings[0]
    assert mode == "keyword_fallback"


def test_repository_failure_returns_empty_results() -> None:
    class BrokenRepository:
        def discover_catalog(self):
            raise RuntimeError("timeout")

    _, datasets, warnings, mode = DiscoveryService(
        BrokenRepository(), FakeGemini()
    ).search("Does study time affect grades?", 8)

    assert datasets == []
    assert "UCI repository unavailable" in warnings[0]
    assert mode == "partial_gemini"
