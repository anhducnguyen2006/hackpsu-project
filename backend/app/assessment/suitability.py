from __future__ import annotations

from app.api.schemas import ResearchAssessment


CRITERION_WEIGHTS = {
    "research_question_and_outcome_alignment": 30,
    "required_variable_coverage": 20,
    "sample_size_considerations": 15,
    "data_quality_and_completeness": 15,
    "documentation_and_provenance": 10,
    "population_and_temporal_relevance": 10,
}


def calculate_final_score(assessment: ResearchAssessment) -> ResearchAssessment:
    available = [
        (key, getattr(assessment.criteria, key))
        for key in CRITERION_WEIGHTS
        if getattr(assessment.criteria, key).score is not None
    ]
    if not available:
        return assessment.model_copy(
            update={
                "final_score": None,
                "score_explanation": (
                    "No scoring criteria had verifiable evidence; a final heuristic "
                    "suitability score is unavailable."
                ),
            }
        )
    weight_total = sum(CRITERION_WEIGHTS[key] for key, _ in available)
    score = round(
        sum(CRITERION_WEIGHTS[key] * criterion.score for key, criterion in available)
        / weight_total
    )
    missing = sorted(set(CRITERION_WEIGHTS) - {key for key, _ in available})
    suffix = (
        f" Unknown criteria were excluded rather than scored: {', '.join(missing)}."
        if missing
        else ""
    )
    return assessment.model_copy(
        update={
            "final_score": score,
            "score_explanation": (
                f"Python recomputed this heuristic score from {len(available)} of "
                f"{len(CRITERION_WEIGHTS)} validated criteria using weights "
                f"{CRITERION_WEIGHTS}.{suffix} This is not an accuracy percentage, "
                "probability, or guarantee of scientific validity."
            ),
        }
    )
