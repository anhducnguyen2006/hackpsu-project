from __future__ import annotations

from app.api.schemas import (
    CategoryCount,
    ColumnProfile,
    DataProfile,
    DatasetAnalysisResponse,
    DatasetResult,
    ExploratoryAnalysisResponse,
    ExploratoryCategory,
    NumericSummary,
    ResearchAssessment,
    ResearchInterpretation,
    SuitabilityCriteria,
    SuitabilityCriterion,
    UCIRecord,
)


DEMO_320 = UCIRecord(
    dataset_id="uci:320",
    title="Student Performance",
    description="Student performance data from secondary education students.",
    repository_url="https://archive.ics.uci.edu/dataset/320/student+performance",
    subject_area="Social Science",
    variables=["studytime", "G3"],
    variable_descriptions={
        "studytime": "weekly study time",
        "G3": "final grade",
    },
    instance_count=649,
    feature_count=30,
    data_available=True,
)

DEMO_45 = UCIRecord(
    dataset_id="uci:45",
    title="Heart Disease",
    description="Heart disease diagnosis dataset.",
    repository_url="https://archive.ics.uci.edu/dataset/45/heart+disease",
    subject_area="Health and Medicine",
    variables=["age", "chol", "num"],
    instance_count=303,
    feature_count=13,
    data_available=True,
)


def demo_search(
    research_question: str,
) -> tuple[ResearchInterpretation, list[DatasetResult], list[str], str]:
    interpretation = ResearchInterpretation(
        original_research_question=research_question,
        research_subject="student academic performance",
        independent_variables=["study time"],
        dependent_variables=["academic performance"],
        target_population="students",
        synonyms=["grades"],
        search_terms=["student", "studytime", "performance"],
    )
    warnings = ["DEMO_MODE: displaying cached verified UCI metadata."]
    question_terms = research_question.lower()
    if not any(term in question_terms for term in ("study", "academic", "student", "grade", "performance")):
        return (
            interpretation,
            [],
            warnings + ["No cached demo result matches this research question."],
            "keyword_fallback",
        )
    results = [
        DatasetResult(
            **DEMO_320.model_dump(),
            data_status="available",
            preliminary_relevance_score=92,
            relevance_explanation="Cached verified UCI metadata matched study time and academic performance.",
            score_confidence="high",
            matched_research_variables=["studytime", "G3"],
            missing_or_unverified_variables=["causal effect"],
            classification="relevant",
        ),
        DatasetResult(
            **DEMO_45.model_dump(),
            data_status="available",
            preliminary_relevance_score=18,
            relevance_explanation="Cached verified UCI metadata is shown as a comparison candidate, not as a direct match.",
            score_confidence="low",
            matched_research_variables=[],
            missing_or_unverified_variables=["study time", "academic performance"],
            classification="partially_relevant",
        ),
    ]
    return interpretation, results, warnings, "keyword_fallback"


def demo_analysis() -> DatasetAnalysisResponse:
    columns = [
        ColumnProfile(
            name="studytime",
            data_type="int64",
            measurement_type="ordinal_or_encoded_numeric",
            missing_count=0,
            missing_fraction=0,
            unique_count=4,
            is_constant=False,
            is_near_empty=False,
            research_roles=["independent"],
            numeric_summary=NumericSummary(count=649, mean=2.0647, median=2),
            categorical_summary=[
                CategoryCount(value=2, count=305),
                CategoryCount(value=1, count=212),
                CategoryCount(value=3, count=97),
                CategoryCount(value=4, count=35),
            ],
        ),
        ColumnProfile(
            name="G3",
            data_type="int64",
            measurement_type="numeric",
            missing_count=0,
            missing_fraction=0,
            unique_count=18,
            is_constant=False,
            is_near_empty=False,
            research_roles=["outcome"],
            numeric_summary=NumericSummary(count=649, mean=11.906, median=11),
        ),
    ]
    profile = DataProfile(
        row_count=649,
        column_count=33,
        column_names=["studytime", "G3"],
        duplicate_row_count=0,
        columns=columns,
        quality_flags=[
            "DEMO_MODE: cached profile from a previous successful UCI retrieval.",
            "Row count is not necessarily the number of independent participants.",
        ],
    )
    criterion = SuitabilityCriterion(score=86, explanation="Cached verified assessment evidence.")
    assessment = ResearchAssessment(
        dataset_summary="Cached assessment for the verified UCI Student Performance dataset.",
        relevant_independent_variables=["studytime"],
        relevant_outcome_variables=["G3"],
        missing_or_unverified_research_variables=["Causal effect"],
        why_useful=["Contains the documented studytime and G3 variables."],
        statistical_methodological_strengths=["649 observed records and complete values for the displayed variables."],
        data_quality_issues=["Cached demo profile; inspect the live source before publication."],
        population_limitations=["Observational student records do not establish causation."],
        sample_size_considerations=["Observed rows are not necessarily independent participants."],
        recommended_further_analyses=["Use an ordinal-aware association analysis."],
        overall_assessment="Cached evidence suggests this dataset is a plausible starting point.",
        criteria=SuitabilityCriteria(
            research_question_and_outcome_alignment=criterion,
            required_variable_coverage=criterion,
            sample_size_considerations=criterion,
            data_quality_and_completeness=criterion,
            documentation_and_provenance=criterion,
            population_and_temporal_relevance=criterion,
        ),
        final_score=86,
        score_explanation="Cached heuristic score from a previous verified assessment; not a probability or guarantee.",
        ai_status="unavailable",
    )
    return DatasetAnalysisResponse(
        dataset=DEMO_320,
        data_status="analyzed",
        profile=profile,
        assessment=assessment,
        ai_assessment_status="unavailable",
        warnings=["DEMO_MODE: showing cached verified statistics; no live Gemini call was made."],
    )


def demo_exploration() -> ExploratoryAnalysisResponse:
    return ExploratoryAnalysisResponse(
        dataset_id="uci:320",
        independent_variable="studytime",
        outcome_variable="G3",
        independent_measurement_type="ordinal_or_encoded_numeric",
        outcome_measurement_type="numeric",
        categories=[
            ExploratoryCategory(category=1, observations=212, mean_outcome=10.84433962264151, median_outcome=11, standard_deviation=3.218624126547874),
            ExploratoryCategory(category=2, observations=305, mean_outcome=12.091803278688525, median_outcome=12, standard_deviation=3.243125070719802),
            ExploratoryCategory(category=3, observations=97, mean_outcome=13.22680412371134, median_outcome=13, standard_deviation=2.502103925695897),
            ExploratoryCategory(category=4, observations=35, mean_outcome=13.057142857142857, median_outcome=13, standard_deviation=3.0384095795513226),
        ],
        missing_independent_count=0,
        missing_outcome_count=0,
        excluded_observation_count=0,
        analyzed_observation_count=649,
        limitations=["DEMO_MODE: cached Pandas results from a previous successful UCI retrieval.", "Descriptive summaries do not establish causation or statistical significance."],
    )
