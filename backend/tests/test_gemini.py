from types import SimpleNamespace

import pytest

from app.api.schemas import RelevanceAssessmentBatch, ResearchInterpretation, UCIRecord
from app.assessment.gemini import GeminiService, GeminiUnavailableError, _thinking_config


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


def test_thinking_config_matches_gemini_model_family() -> None:
    from google.genai import types

    modern = _thinking_config(types, "gemini-3.8-flash")
    legacy = _thinking_config(types, "gemini-2.5-flash")

    assert modern is not None
    assert modern.thinking_level == types.ThinkingLevel.LOW
    assert legacy is not None
    assert legacy.thinking_budget == 0


class FakeClient:
    def __init__(self, response):
        self.models = SimpleNamespace(generate_content=lambda **_: response)


def _interpretation_response(**overrides):
    payload = {
        "original_research_question": "How does pollution affect health?",
        "refined_question": "What is the relationship between pollution exposure and health outcomes?",
        "research_subject": "pollution and health",
        "independent_variables": ["pollution exposure"],
        "dependent_variables": ["health outcomes"],
        "target_population": None,
        "population": None,
        "geographic_scope": None,
        "temporal_scope": None,
        "synonyms": ["environmental exposure", "health outcome"],
        "assumptions_or_ambiguities": ["Pollution type is unspecified."],
        "search_terms": ["pollution", "exposure", "health outcomes"],
    }
    payload.update(overrides)
    return SimpleNamespace(parsed=payload, text=None, candidates=[SimpleNamespace(finish_reason="STOP")])


def test_interpretation_preserves_ambiguity_and_missing_geography() -> None:
    result = GeminiService(FakeClient(_interpretation_response())).interpret(
        "How does pollution affect health?"
    )
    assert result.refined_question
    assert result.geographic_scope is None
    assert "unspecified" in result.assumptions_or_ambiguities[0]
    assert result.target_population is None


def test_interpretation_supports_specific_and_non_causal_questions() -> None:
    response = _interpretation_response(
        original_research_question="What patterns of sleep and mood are reported by adults in Canada from 2020 to 2022?",
        refined_question="What patterns exist between sleep and reported mood among adults in Canada from 2020 to 2022?",
        independent_variables=[],
        dependent_variables=[],
        target_population="adults",
        population="adults",
        geographic_scope="Canada",
        assumptions_or_ambiguities=[],
    )
    result = GeminiService(FakeClient(response)).interpret(
        "What patterns of sleep and mood are reported by adults in Canada from 2020 to 2022?"
    )
    assert result.independent_variables == []
    assert result.dependent_variables == []
    assert result.geographic_scope == "Canada"


def test_interpretation_cache_makes_exactly_one_gemini_call() -> None:
    calls = 0

    def generate_content(**_):
        nonlocal calls
        calls += 1
        return _interpretation_response()

    service = GeminiService(SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    first = service.interpret("  How does pollution affect health?  ")
    second = service.interpret("How does pollution affect health?")
    assert first == second
    assert calls == 1


def test_interpretation_unavailable_raises_without_inventing_refinement() -> None:
    with pytest.raises(GeminiUnavailableError):
        GeminiService().interpret("How does pollution affect health?")


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
