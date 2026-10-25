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
    ResearchVariableEvidence,
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

DEMO_856 = UCIRecord(
    dataset_id="uci:856",
    title="Higher Education Students Performance Evaluation",
    description=(
        "The data was collected from Faculty of Engineering and Faculty of "
        "Educational Sciences students in 2019 to predict end-of-term performance."
    ),
    repository_url=(
        "https://archive.ics.uci.edu/dataset/856/"
        "higher+education+students+performance+evaluation"
    ),
    subject_area="Social Science",
    variables=[
        "Student Age",
        "Weekly study hours",
        "Cumulative grade point average in the last semester (/4.00)",
        "OUTPUT Grade",
    ],
    variable_descriptions={
        "Weekly study hours": "1: None, 2: <5 hours, 3: 6-10 hours, 4: 11-20 hours, 5: more than 20 hours",
        "OUTPUT Grade": "0: Fail, 1: DD, 2: DC, 3: CC, 4: CB, 5: BB, 6: BA, 7: AA",
    },
    instance_count=145,
    feature_count=31,
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
            **DEMO_856.model_dump(),
            data_status="available",
            preliminary_relevance_score=48,
            relevance_explanation=(
                "Cached verified UCI metadata shows an education-performance "
                "comparison candidate with documented weekly study-hour and grade variables."
            ),
            score_confidence="low",
            matched_research_variables=["Weekly study hours", "OUTPUT Grade"],
            missing_or_unverified_variables=["Directly comparable study-time coding", "Causal effect"],
            classification="partially_relevant",
        ),
    ]
    return interpretation, results, warnings, "keyword_fallback"


def demo_analysis() -> DatasetAnalysisResponse:
    columns = [
        ColumnProfile(
            name="studytime",
            variable_description="weekly study time",
            data_type="int64",
            measurement_type="ordinal",
            missing_count=0,
            missing_fraction=0,
            unique_count=4,
            is_constant=False,
            is_near_empty=False,
            research_roles=["independent"],
            numeric_summary=NumericSummary(
                count=649,
                mean=1.9306625577812018,
                median=2,
                standard_deviation=0.829509574636615,
                minimum=1,
                percentile_25=1,
                percentile_75=2,
                maximum=4,
            ),
            categorical_summary=[
                CategoryCount(value=2, count=305),
                CategoryCount(value=1, count=212),
                CategoryCount(value=3, count=97),
                CategoryCount(value=4, count=35),
            ],
        ),
        ColumnProfile(
            name="G3",
            variable_description="final grade",
            data_type="int64",
            measurement_type="continuous",
            missing_count=0,
            missing_fraction=0,
            unique_count=18,
            is_constant=False,
            is_near_empty=False,
            research_roles=["outcome"],
            numeric_summary=NumericSummary(
                count=649,
                mean=11.906009244992296,
                median=12,
                standard_deviation=3.230656242804805,
                minimum=0,
                percentile_25=10,
                percentile_75=14,
                maximum=19,
            ),
        ),
    ]
    profile = DataProfile(
        row_count=649,
        column_count=33,
        column_names=["studytime", "G3"],
        duplicate_row_count=0,
        columns=columns,
        research_variable_evidence=[
            ResearchVariableEvidence(
                research_variable="study time",
                matched_columns=["studytime"],
                usable_observations=649,
                notes=[
                    "Verified UCI codebook mapping: studytime is weekly study time encoded from 1 to 4."
                ],
            ),
            ResearchVariableEvidence(
                research_variable="academic performance",
                matched_columns=["G3"],
                usable_observations=649,
                notes=[
                    "Verified UCI codebook mapping: G3 is the final grade on a 0–20 scale."
                ],
            ),
        ],
        quality_flags=[
            "DEMO_MODE: cached Pandas profile from a previous successful UCI retrieval.",
            "Row count is not necessarily the number of independent participants.",
        ],
    )
    unavailable_criterion = SuitabilityCriterion(
        score=None,
        explanation="Unavailable: no verifiable cached AI assessment is present.",
    )
    assessment = ResearchAssessment(
        dataset_summary="Verified cached profile for the UCI Student Performance dataset.",
        relevant_independent_variables=["studytime"],
        relevant_outcome_variables=["G3"],
        missing_or_unverified_research_variables=["Causal effect"],
        why_useful=["Verified profile contains the documented studytime and G3 variables."],
        statistical_methodological_strengths=["649 observed records and complete values for the displayed variables."],
        data_quality_issues=["Cached profile; inspect the live source before publication."],
        population_limitations=["Observational student records do not establish causation."],
        sample_size_considerations=["Observed rows are not necessarily independent participants."],
        recommended_further_analyses=["Use an ordinal-aware association analysis."],
        overall_assessment="AI assessment unavailable. The verified statistical profile is available for review.",
        criteria=SuitabilityCriteria(
            research_question_and_outcome_alignment=unavailable_criterion,
            required_variable_coverage=unavailable_criterion,
            sample_size_considerations=unavailable_criterion,
            data_quality_and_completeness=unavailable_criterion,
            documentation_and_provenance=unavailable_criterion,
            population_and_temporal_relevance=unavailable_criterion,
        ),
        final_score=None,
        score_explanation="No verifiable cached AI assessment is available; no suitability score is reported.",
        ai_status="unavailable",
    )
    return DatasetAnalysisResponse(
        dataset=DEMO_320,
        data_status="analyzed",
        profile=profile,
        assessment=assessment,
        ai_assessment_status="unavailable",
        warnings=[
            "DEMO_MODE: showing cached verified Pandas statistics; no live Gemini call was made.",
            "AI assessment unavailable: no authentic cached Gemini assessment is present.",
        ],
    )


def demo_exploration() -> ExploratoryAnalysisResponse:
    return ExploratoryAnalysisResponse(
        dataset_id="uci:320",
        independent_variable="studytime",
        outcome_variable="G3",
        independent_measurement_type="ordinal",
        outcome_measurement_type="continuous",
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
