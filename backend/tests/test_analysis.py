import pandas as pd
import pytest

from app.api.schemas import (
    AnalysisRequest,
    RelevanceAssessmentBatch,
    ResearchAssessment,
    ResearchInterpretation,
    SuitabilityCriteria,
    SuitabilityCriterion,
    UCIRecord,
)
from app.analysis.service import DatasetAnalysisService
from app.analysis.exploratory import ExploratoryAnalyzer, ExploratoryAnalysisError
from app.demo import demo_analysis
from app.profiling.profiler import DataProfiler


def interpretation() -> ResearchInterpretation:
    return ResearchInterpretation(
        original_research_question="Does study time affect academic performance?",
        research_subject="student academic performance",
        independent_variables=["study time"],
        dependent_variables=["grades"],
        target_population="students",
        synonyms=[],
        search_terms=["study", "grades", "students"],
    )


def assessment() -> ResearchAssessment:
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
    def __init__(self) -> None:
        self.fetch_calls = 0
        self.metadata = UCIRecord(
            dataset_id="uci:320",
            title="Student Performance",
            description="Student performance dataset.",
            repository_url="https://archive.ics.uci.edu/dataset/320",
            variables=["studytime", "G3"],
            variable_descriptions={
                "studytime": "weekly study time",
                "G3": "final grade",
            },
            data_available=True,
        )

    def get_metadata(self, dataset_id: int) -> UCIRecord:
        return self.metadata

    def fetch_dataset(self, dataset_id: int):
        self.fetch_calls += 1
        return self.metadata, pd.DataFrame(
            {"studytime": [1, 2, 3], "G3": [10, 12, 15]}
        ), {}


class FakeGemini:
    def __init__(self) -> None:
        self.interpret_calls = 0
        self.assessment_calls = 0

    def interpret(self, question: str):
        self.interpret_calls += 1
        return interpretation()

    def assess_suitability(self, question, parsed, dataset, profile):
        self.assessment_calls += 1
        assert profile.row_count == 3
        return assessment()


def test_profile_marks_ordinal_values_and_matches_verified_columns() -> None:
    profile = DataProfiler().profile(
        pd.DataFrame({"studytime": [1, 2, 3], "G3": [10, 12, 15]}),
        interpretation(),
        {"studytime": "weekly study time", "G3": "final grade"},
    )
    studytime = next(column for column in profile.columns if column.name == "studytime")
    assert studytime.measurement_type == "ordinal"
    assert studytime.numeric_summary is None
    assert [(item.value, item.count) for item in studytime.categorical_summary] == [
        (1, 1),
        (2, 1),
        (3, 1),
    ]
    assert "independent" in studytime.research_roles
    assert profile.row_count == 3
    assert any(
        item.research_variable == "study time"
        and item.matched_columns == ["studytime"]
        for item in profile.research_variable_evidence
    )


def test_profile_marks_integer_quantities_as_discrete_numeric() -> None:
    profile = DataProfiler().profile(
        pd.DataFrame({"age": [45, 52, 60, None], "creatinine": [1.2, 1.4, 1.8, 2.1]}),
        variable_descriptions={"age": "age of the patient", "creatinine": "serum creatinine"},
    )

    age = next(column for column in profile.columns if column.name == "age")
    creatinine = next(column for column in profile.columns if column.name == "creatinine")

    assert age.measurement_type == "discrete_numeric"
    assert age.numeric_summary is not None
    assert creatinine.measurement_type == "continuous"


def test_profile_preserves_declared_categorical_measurement() -> None:
    profile = DataProfiler().profile(
        pd.DataFrame({"chest-pain": [1, 2, 3, 4], "ecg": [0, 1, 2, 2]}),
        variable_descriptions={
            "chest-pain": "chest pain type",
            "ecg": "resting electrocardiographic results",
        },
        variable_types={"chest-pain": "Categorical", "ecg": "Categorical"},
    )

    assert [column.measurement_type for column in profile.columns] == [
        "categorical",
        "categorical",
    ]
    assert all(column.numeric_summary is None for column in profile.columns)


def test_analysis_is_cached_and_score_is_python_recomputed() -> None:
    repository = FakeRepository()
    gemini = FakeGemini()
    service = DatasetAnalysisService(repository, gemini)
    request = AnalysisRequest(research_question="Does study time affect academic performance?")

    first = service.analyze("uci:320", request)
    second = service.analyze("uci:320", request)

    assert first.model_dump() == second.model_dump()
    assert repository.fetch_calls == 1
    assert gemini.interpret_calls == 0
    assert gemini.assessment_calls == 1
    assert first.assessment is not None
    assert first.assessment.final_score == 80


def test_analysis_reuses_fetched_dataset_and_profile_for_changed_question() -> None:
    repository = FakeRepository()
    service = DatasetAnalysisService(repository, FakeGemini())

    service.analyze("uci:320", AnalysisRequest(research_question="Does study time affect grades?"))
    service.analyze(
        "uci:320",
        AnalysisRequest(research_question="Does weekly study time affect academic performance?"),
    )

    assert repository.fetch_calls == 1


def test_demo_analysis_reports_only_verified_statistics() -> None:
    response = demo_analysis()

    assert response.ai_assessment_status == "unavailable"
    assert response.assessment is not None
    assert response.assessment.final_score is None
    assert all(
        criterion["score"] is None
        for criterion in response.assessment.criteria.model_dump().values()
    )
    g3 = next(column for column in response.profile.columns if column.name == "G3")
    assert g3.numeric_summary is not None
    assert g3.numeric_summary.mean == pytest.approx(11.906009244992296)
    assert g3.numeric_summary.median == 12
    studytime = next(
        column for column in response.profile.columns if column.name == "studytime"
    )
    assert studytime.numeric_summary is not None
    assert studytime.numeric_summary.mean == pytest.approx(1.9306625577812018)
    assert {item.research_variable for item in response.profile.research_variable_evidence} == {
        "study time",
        "academic performance",
    }


def test_invalid_dataset_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        DatasetAnalysisService(FakeRepository(), FakeGemini()).analyze(
            "https://untrusted.example/data.csv",
            AnalysisRequest(research_question="Does study time affect academic performance?"),
        )


def test_data_failure_returns_metadata_only() -> None:
    class BrokenRepository(FakeRepository):
        def fetch_dataset(self, dataset_id: int):
            raise RuntimeError("download failed")

    response = DatasetAnalysisService(BrokenRepository(), FakeGemini()).analyze(
        "uci:320",
        AnalysisRequest(research_question="Does study time affect academic performance?"),
    )
    assert response.data_status == "metadata_only"
    assert response.profile is None
    assert response.assessment is None


def test_gemini_failure_preserves_verified_profile() -> None:
    class BrokenAssessmentGemini(FakeGemini):
        def assess_suitability(self, question, parsed, dataset, profile):
            raise RuntimeError("temporary Gemini failure")

    response = DatasetAnalysisService(
        FakeRepository(), BrokenAssessmentGemini()
    ).analyze(
        "uci:320",
        AnalysisRequest(research_question="Does study time affect academic performance?"),
    )
    assert response.data_status == "analyzed"
    assert response.profile is not None
    assert response.assessment is None
    assert response.ai_assessment_status == "unavailable"
    assert any("AI suitability assessment unavailable" in warning for warning in response.warnings)


def test_python_recomputes_final_score_from_criteria() -> None:
    from app.assessment.suitability import calculate_final_score

    scored = calculate_final_score(assessment())
    assert scored.final_score == 80
    assert "Python recomputed" in scored.score_explanation


def test_malformed_gemini_assessment_keeps_profile(monkeypatch) -> None:
    class MalformedGemini(FakeGemini):
        def assess_suitability(self, question, parsed, dataset, profile):
            return {"not": "a valid ResearchAssessment"}

    response = DatasetAnalysisService(FakeRepository(), MalformedGemini()).analyze(
        "uci:320",
        AnalysisRequest(research_question="Does study time affect academic performance?"),
    )
    assert response.profile is not None
    assert response.assessment is None
    assert response.ai_assessment_status == "unavailable"


def test_exploratory_analysis_computes_ordinal_group_statistics() -> None:
    response = ExploratoryAnalyzer().analyze(
        "uci:320",
        pd.DataFrame({"studytime": [1, 1, 2, 2, 3, None], "G3": [10, 14, 12, 16, 18, 20]}),
        "studytime",
        "G3",
    )
    assert response.independent_measurement_type == "ordinal"
    assert response.analyzed_observation_count == 5
    assert response.excluded_observation_count == 1
    assert [(item.category, item.observations, item.mean_outcome) for item in response.categories] == [
        (1, 2, 12.0),
        (2, 2, 14.0),
        (3, 1, 18.0),
    ]
    assert response.categories[0].median_outcome == 12.0
    assert response.categories[0].standard_deviation is not None


def test_exploratory_analysis_rejects_unverified_or_incompatible_variables() -> None:
    dataframe = pd.DataFrame({"group": ["a", "b"], "outcome": ["high", "low"]})
    with pytest.raises(ExploratoryAnalysisError, match="not verified"):
        ExploratoryAnalyzer().analyze("uci:1", dataframe, "missing", "outcome")
    with pytest.raises(ExploratoryAnalysisError, match="numeric"):
        ExploratoryAnalyzer().analyze("uci:1", dataframe, "group", "outcome")
