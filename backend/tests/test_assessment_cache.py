from __future__ import annotations

import pandas as pd

from app.api.schemas import (
    AnalysisRequest,
    ResearchAssessment,
    ResearchInterpretation,
    SuitabilityCriteria,
    SuitabilityCriterion,
    UCIRecord,
)
from app.analysis.service import DatasetAnalysisService


def _interpretation(question: str) -> ResearchInterpretation:
    return ResearchInterpretation(
        original_research_question=question,
        refined_question="study time and academic performance",
        research_subject="student performance",
        independent_variables=["study time"],
        dependent_variables=["grades"],
        target_population="students",
        synonyms=[],
        search_terms=["study", "grades", "students"],
    )


def _assessment() -> ResearchAssessment:
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
    return ResearchAssessment(
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


class FakeRepository:
    def __init__(self, dataframe: pd.DataFrame | None = None) -> None:
        self.dataframe = dataframe if dataframe is not None else pd.DataFrame(
            {"studytime": [1, 2, 3], "G3": [10, 12, 15]}
        )
        self.metadata = UCIRecord(
            dataset_id="uci:320",
            title="Student Performance",
            description="Student performance dataset.",
            repository_url="https://archive.ics.uci.edu/dataset/320",
            variables=["studytime", "G3"],
            variable_descriptions={"studytime": "weekly study time", "G3": "final grade"},
            data_available=True,
        )

    def get_metadata(self, dataset_id: int) -> UCIRecord:
        return self.metadata

    def fetch_dataset(self, dataset_id: int):
        return self.metadata, self.dataframe, {}


class FakeGemini:
    def __init__(self, assessment_result: object | None = None) -> None:
        self.assessment_calls = 0
        self.assessment_result = assessment_result or _assessment()

    def interpret(self, question: str) -> ResearchInterpretation:
        return _interpretation(question)

    def assess_suitability(self, question, interpretation, dataset, profile):
        self.assessment_calls += 1
        return self.assessment_result


def _request(question: str = "Does study time affect grades?") -> AnalysisRequest:
    return AnalysisRequest(research_question=question)


def _patch_profile_storage(monkeypatch) -> None:
    monkeypatch.setattr("app.analysis.service.upsert_dataset", lambda dataset: 320)
    monkeypatch.setattr("app.analysis.service.get_dataset_profile", lambda *args: None)
    monkeypatch.setattr("app.analysis.service.save_dataset_profile", lambda *args, **kwargs: 1)


def _patch_assessment_storage(monkeypatch, cache: dict[str, dict]) -> None:
    monkeypatch.setattr(
        "app.analysis.service.get_cached_research_assessment",
        lambda cache_key: cache.get(cache_key),
    )
    monkeypatch.setattr(
        "app.analysis.service.save_research_assessment",
        lambda **kwargs: cache.__setitem__(
            kwargs["cache_key"], kwargs["assessment"].model_dump(mode="json")
        ) or 1,
    )


def test_assessment_cache_hit_skips_gemini(monkeypatch) -> None:
    _patch_profile_storage(monkeypatch)
    cache: dict[str, dict] = {}
    _patch_assessment_storage(monkeypatch, cache)
    repository = FakeRepository()
    first_gemini = FakeGemini()
    DatasetAnalysisService(repository, first_gemini).analyze("uci:320", _request())
    second_gemini = FakeGemini()

    response = DatasetAnalysisService(repository, second_gemini).analyze(
        "uci:320", _request()
    )

    assert response.assessment is not None
    assert first_gemini.assessment_calls == 1
    assert second_gemini.assessment_calls == 0


def test_changed_question_misses_exact_assessment_cache(monkeypatch) -> None:
    _patch_profile_storage(monkeypatch)
    cache: dict[str, dict] = {}
    _patch_assessment_storage(monkeypatch, cache)
    repository = FakeRepository()
    first_gemini = FakeGemini()
    DatasetAnalysisService(repository, first_gemini).analyze("uci:320", _request())
    second_gemini = FakeGemini()

    DatasetAnalysisService(repository, second_gemini).analyze(
        "uci:320", _request("Does weekly study time affect final grades?")
    )

    assert second_gemini.assessment_calls == 1


def test_changed_prompt_version_misses_assessment_cache(monkeypatch) -> None:
    _patch_profile_storage(monkeypatch)
    cache: dict[str, dict] = {}
    _patch_assessment_storage(monkeypatch, cache)
    repository = FakeRepository()
    DatasetAnalysisService(repository, FakeGemini()).analyze("uci:320", _request())
    monkeypatch.setattr(
        "app.analysis.service.GeminiService.SUITABILITY_PROMPT_VERSION",
        "suitability-prompt-v2",
    )
    second_gemini = FakeGemini()

    DatasetAnalysisService(repository, second_gemini).analyze("uci:320", _request())

    assert second_gemini.assessment_calls == 1


def test_changed_profile_misses_assessment_cache(monkeypatch) -> None:
    _patch_profile_storage(monkeypatch)
    cache: dict[str, dict] = {}
    _patch_assessment_storage(monkeypatch, cache)
    repository = FakeRepository()
    DatasetAnalysisService(repository, FakeGemini()).analyze("uci:320", _request())
    repository.dataframe = pd.DataFrame({"studytime": [1, 2, 4], "G3": [10, 12, 20]})
    second_gemini = FakeGemini()

    DatasetAnalysisService(repository, second_gemini).analyze("uci:320", _request())

    assert second_gemini.assessment_calls == 1


def test_assessment_cache_database_failure_does_not_block_gemini(monkeypatch) -> None:
    _patch_profile_storage(monkeypatch)
    monkeypatch.setattr(
        "app.analysis.service.get_cached_research_assessment",
        lambda cache_key: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    monkeypatch.setattr(
        "app.analysis.service.save_research_assessment",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    gemini = FakeGemini()

    response = DatasetAnalysisService(FakeRepository(), gemini).analyze(
        "uci:320", _request()
    )

    assert response.assessment is not None
    assert gemini.assessment_calls == 1
    assert any("cache unavailable" in warning for warning in response.warnings)


def test_invalid_gemini_assessment_is_not_cached(monkeypatch) -> None:
    _patch_profile_storage(monkeypatch)
    cache: dict[str, dict] = {}
    _patch_assessment_storage(monkeypatch, cache)
    gemini = FakeGemini(assessment_result=None)
    gemini.assessment_result = {"malformed": True}

    response = DatasetAnalysisService(FakeRepository(), gemini).analyze(
        "uci:320", _request()
    )

    assert response.assessment is None
    assert cache == {}
    assert any("AI suitability assessment unavailable" in warning for warning in response.warnings)
