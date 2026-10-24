from types import SimpleNamespace

import pytest

from app.api.schemas import RelevanceAssessmentBatch, ResearchInterpretation, UCIRecord
from app.assessment.gemini import GeminiService, GeminiUnavailableError


def _interpretation() -> ResearchInterpretation:
    return ResearchInterpretation(
        original_research_question="Does study time affect grades?",
        research_subject="student performance",
        independent_variables=["study time"],
        dependent_variables=["grades"],
        target_population="students",
        synonyms=["academic performance"],
        search_terms=["study", "grades", "students"],
    )


def _candidate(index: int) -> UCIRecord:
    return UCIRecord(
        dataset_id=f"uci:{index}",
        title=f"Student performance dataset {index}",
        description="Verified education metadata.",
        repository_url=f"https://archive.ics.uci.edu/dataset/{index}",
        variables=["studytime", "G3"],
    )


class FakeClient:
    def __init__(self, response):
        self.models = SimpleNamespace(generate_content=lambda **_: response)


def test_reranking_parses_maximum_sized_valid_structured_response() -> None:
    assessments = [
        {
            "dataset_id": f"uci:{index}",
            "preliminary_relevance_score": 50 + index,
            "score_confidence": "medium",
            "relevance_explanation": "Verified education outcome and variable metadata match.",
            "matched_research_variables": ["studytime", "G3"],
            "missing_or_unverified_variables": ["causal effect"],
            "classification": "relevant",
        }
        for index in range(1, 13)
    ]
    response = SimpleNamespace(
        parsed={"assessments": assessments},
        text=None,
        candidates=[SimpleNamespace(finish_reason="STOP")],
        usage_metadata=SimpleNamespace(
            prompt_token_count=1200,
            candidates_token_count=1200,
            total_token_count=2400,
        ),
    )
    result = GeminiService(FakeClient(response)).rerank(
        "Does study time affect grades?",
        _interpretation(),
        [_candidate(index) for index in range(1, 13)],
    )
    assert len(result.assessments) == 12


def test_reranking_rejects_truncated_response() -> None:
    response = SimpleNamespace(
        parsed=None,
        text='{"assessments": [',
        candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")],
    )
    with pytest.raises(GeminiUnavailableError, match="truncated"):
        GeminiService(FakeClient(response)).rerank(
            "Does study time affect grades?",
            _interpretation(),
            [_candidate(index) for index in range(1, 13)],
        )
