from types import SimpleNamespace

import pandas as pd
import pytest

from app.api.schemas import (
    RelevanceAssessmentBatch,
    ResearchAssessment,
    ResearchInterpretation,
    SuitabilityCriteria,
    SuitabilityCriterion,
    UCIRecord,
)
from app.assessment.gemini import (
    GeminiService,
    GeminiUnavailableError,
    _thinking_config,
    _interpret_thinking_config,
)
from app.config import settings
from app.profiling.profiler import DataProfiler


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


def _assessment_response():
    criteria = {
        key: SuitabilityCriterion(score=80, explanation="Verified evidence.")
        for key in (
            "research_question_and_outcome_alignment",
            "required_variable_coverage",
            "sample_size_considerations",
            "data_quality_and_completeness",
            "documentation_and_provenance",
            "population_and_temporal_relevance",
        )
    }
    assessment = ResearchAssessment(
        dataset_summary="Verified tabular dataset.",
        relevant_independent_variables=["studytime"],
        relevant_outcome_variables=["G3"],
        missing_or_unverified_research_variables=[],
        why_useful=["Contains verified variables."],
        statistical_methodological_strengths=["Adequate observations."],
        data_quality_issues=[],
        population_limitations=[],
        sample_size_considerations=["Row count is not independent participant count."],
        recommended_further_analyses=["Use an ordinal-aware analysis."],
        overall_assessment="Potentially useful for an observational analysis.",
        criteria=SuitabilityCriteria(**criteria),
        final_score=None,
        score_explanation="Python will calculate this.",
        ai_status="available",
    )
    return SimpleNamespace(
        parsed=assessment.model_dump(mode="json"),
        text=None,
        candidates=[SimpleNamespace(finish_reason="STOP")],
    )


def _suitability_inputs():
    from app.profiling.profiler import DataProfiler

    interpretation = _interpretation()
    profile = DataProfiler().profile(
        pd.DataFrame({"studytime": [1, 2, 3], "G3": [10, 12, 15]}),
        interpretation,
    )
    return interpretation, _candidate(320), profile


def test_interpret_thinking_config_matches_gemini_3_model() -> None:
    from google.genai import types

    modern = _thinking_config(types, "gemini-3.8-flash")
    legacy = _thinking_config(types, "gemini-2.5-flash")

    assert modern is not None
    assert modern.thinking_level == types.ThinkingLevel.LOW
    assert legacy is not None
    assert legacy.thinking_budget == 0


def test_interpret_supplies_thinking_config(monkeypatch) -> None:
    from google.genai import types

    captured = {}

    def generate_content(**kwargs):
        captured.update(kwargs)
        return _interpretation_response()

    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")
    monkeypatch.setattr(settings, "gemini_interpret_thinking_level", "low")
    GeminiService(
        SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    ).interpret("How does pollution affect health?")

    config = captured["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is ResearchInterpretation
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW


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


def test_suitability_profile_compaction_preserves_verified_relevant_detail() -> None:
    profile = DataProfiler().profile(
        pd.DataFrame(
            {
                "studytime": [1, 2, 3, 4],
                "G3": [10, 12, 15, 18],
                "unrelated_measurement": [100, 200, 300, 400],
            }
        ),
        _interpretation(),
        {"studytime": "weekly study time", "G3": "final grade"},
    )

    compact = GeminiService._compact_profile(profile)
    columns = {column["name"]: column for column in compact["columns"]}

    assert compact["row_count"] == profile.row_count
    assert "categorical_summary" in columns["studytime"]
    assert "unrelated_measurement" not in columns
    assert "unrelated_measurement" in compact["all_column_names"]


def test_suitability_falls_back_after_transient_503(monkeypatch) -> None:
    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            raise RuntimeError("503 UNAVAILABLE")
        return _assessment_response()

    monkeypatch.setattr(settings, "gemini_model", "primary-model")
    monkeypatch.setattr(settings, "gemini_fallback_model", "fallback-model")
    monkeypatch.setattr(settings, "gemini_overall_timeout_ms", 20000)
    monkeypatch.setattr(settings, "gemini_fallback_reserve_ms", 10000)
    interpretation, dataset, profile = _suitability_inputs()
    result = GeminiService(
        SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    ).assess_suitability("Does study time affect grades?", interpretation, dataset, profile)

    assert result.criteria.required_variable_coverage.score == 80
    assert calls == ["primary-model", "fallback-model"]


def test_suitability_falls_back_after_transient_504_then_reports_failure(monkeypatch) -> None:
    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        raise RuntimeError("504 DEADLINE_EXCEEDED")

    monkeypatch.setattr(settings, "gemini_model", "primary-model")
    monkeypatch.setattr(settings, "gemini_fallback_model", "fallback-model")
    monkeypatch.setattr(settings, "gemini_overall_timeout_ms", 20000)
    monkeypatch.setattr(settings, "gemini_fallback_reserve_ms", 10000)
    interpretation, dataset, profile = _suitability_inputs()

    with pytest.raises(GeminiUnavailableError) as error:
        GeminiService(
            SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        ).assess_suitability("Does study time affect grades?", interpretation, dataset, profile)

    assert error.value.category == "provider_http_504"
    assert calls == ["primary-model", "fallback-model"]


def test_suitability_does_not_fallback_on_quota_error(monkeypatch) -> None:
    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")

    monkeypatch.setattr(settings, "gemini_model", "primary-model")
    monkeypatch.setattr(settings, "gemini_fallback_model", "fallback-model")
    interpretation, dataset, profile = _suitability_inputs()

    with pytest.raises(GeminiUnavailableError) as error:
        GeminiService(
            SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        ).assess_suitability("Does study time affect grades?", interpretation, dataset, profile)

    assert error.value.category == "quota/rate limit (not retried)"
    assert calls == ["primary-model"]


def test_suitability_skips_fallback_when_remaining_deadline_is_below_provider_minimum(monkeypatch) -> None:
    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(settings, "gemini_model", "primary-model")
    monkeypatch.setattr(settings, "gemini_fallback_model", "fallback-model")
    monkeypatch.setattr(settings, "gemini_overall_timeout_ms", 16000)
    monkeypatch.setattr(settings, "gemini_fallback_reserve_ms", 6000)
    monkeypatch.setattr(settings, "gemini_provider_min_timeout_ms", 20000)
    interpretation, dataset, profile = _suitability_inputs()

    with pytest.raises(GeminiUnavailableError):
        GeminiService(
            SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        ).assess_suitability("Does study time affect grades?", interpretation, dataset, profile)

    assert calls == ["primary-model"]


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
