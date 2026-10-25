# API Reference

Last verified: 2026-10-24

Base URL: `http://localhost:8000/api/v1`. Authentication is not implemented. CORS is configured from `BACKEND_CORS_ORIGINS`.

## `GET /health`

Returns process health.

Response `200`:

```json
{"status": "ok"}
```

## `POST /discovery/search`

Searches verified repository metadata for a natural-language research question. Gemini interprets the question when available; normal candidate ranking uses local embedding similarity across the full question and independently extracted research concepts. If Gemini is unavailable, deterministic concept extraction remains explicit in `processing_mode` and `warnings`.

Each result may include additive `concept_matches` evidence. Semantic scores are ranking signals over verified metadata, not scientific-suitability probabilities. Concept scores are fused as full question (0.45), independent variables (0.25), dependent variables (0.20), and context/subject/synonyms/search terms (0.10); unavailable groups are renormalized so datasets matching only one research variable remain eligible.

Request:

```json
{
  "research_question": "Does study time affect students' academic performance?",
  "limit": 8
}
```

`research_question` is 10–2000 characters. `limit` is 1–25 and defaults to 8.

Response shape:

```json
{
  "interpretation": {
    "original_research_question": "Does study time affect students' academic performance?",
    "research_subject": "student academic performance",
    "independent_variables": ["study time"],
    "dependent_variables": ["academic performance"],
    "target_population": "students",
    "synonyms": ["grades"],
    "search_terms": ["student", "studytime", "performance"]
  },
  "datasets": [{
    "dataset_id": "uci:320",
    "title": "Student Performance",
    "description": "Student performance data from secondary education students.",
    "repository_url": "https://archive.ics.uci.edu/dataset/320/student+performance",
    "subject_area": "Social Science",
    "variables": ["studytime", "G3"],
    "variable_descriptions": {
      "studytime": "weekly study time",
      "G3": "final grade"
    },
    "instance_count": 649,
    "feature_count": 30,
    "data_available": true,
    "source": "UCI Machine Learning Repository",
    "data_status": "available",
    "preliminary_relevance_score": 92,
    "relevance_explanation": "Verified metadata matched the question.",
    "score_confidence": "high",
    "matched_research_variables": ["studytime", "G3"],
    "missing_or_unverified_variables": ["causal effect"],
    "classification": "relevant"
  }],
  "explanation": "Results are ranked using verified UCI metadata.",
  "warnings": [],
  "processing_mode": "gemini"
}
```

`processing_mode` is `gemini`, `partial_gemini`, or `keyword_fallback`. Preliminary relevance is metadata-based and is not research suitability.

Errors include `422` for invalid request validation. Repository failure is returned as an empty result with a warning; the route does not fabricate records.

### DEMO_MODE

With `DEMO_MODE=true`, this route returns cached verified metadata for UCI #320 and #856 for education-related questions. It does not perform a live UCI search or claim live Gemini generation. Unmatched questions return no cached records.

## `POST /datasets/{dataset_id}/analyze`

Analyzes a verified UCI dataset. `dataset_id` must use `uci:<positive integer>`.

Request:

```json
{"research_question": "Does study time affect students' academic performance?"}
```

The response contains:

- `dataset`: verified UCI metadata
- `data_status`: `analyzed`, `metadata_only`, or `failed`
- `profile`: deterministic Pandas profile when tabular retrieval succeeds
- `assessment`: optional Gemini assessment with Python-recomputed heuristic score
- `ai_assessment_status`: `available` or `unavailable`
- `warnings`

The profile includes row/column counts, dtypes, missingness, duplicate rows, numeric summaries, categorical summaries, measurement labels, research-variable evidence, correlations, and quality flags. Gemini receives verified metadata and this computed profile; it does not calculate the statistics.

Errors:

- `400` for malformed or non-UCI dataset IDs
- `502` for UCI repository failures
- `422` for invalid request bodies

If data retrieval fails, verified metadata is preserved as `metadata_only`. If Gemini fails, the deterministic profile is preserved and the AI assessment is unavailable.

## `POST /datasets/{dataset_id}/explore`

Computes grouped descriptive statistics for a verified independent variable and numeric outcome.

Request:

```json
{
  "research_question": "Does study time affect students' academic performance?",
  "independent_variable": "studytime",
  "outcome_variable": "G3"
}
```

Response example:

```json
{
  "dataset_id": "uci:320",
  "independent_variable": "studytime",
  "outcome_variable": "G3",
  "independent_measurement_type": "ordinal",
  "outcome_measurement_type": "numeric",
  "categories": [{
    "category": 1,
    "observations": 212,
    "mean_outcome": 10.84433962264151,
    "median_outcome": 11.0,
    "standard_deviation": 3.218624126547874
  }],
  "missing_independent_count": 0,
  "missing_outcome_count": 0,
  "excluded_observation_count": 0,
  "analyzed_observation_count": 649,
  "limitations": [
    "These are descriptive group summaries, not a causal analysis."
  ]
}
```

The actual response includes all categories and limitations. Invalid columns, nonnumeric outcomes, too many independent categories, or fewer than two categories produce `400`. In DEMO_MODE only the cached `studytime`/`G3` analysis for #320 is supported.

## Development endpoint

`GET /dev/dataset-test` is a development-only proof of concept for UCI #320. It retrieves metadata and the original DataFrame and returns JSON-safe profiling output. It is not a general discovery endpoint.

## Operational limitations

There is no authentication, pagination, persistent job system, streaming response, or background worker. External calls are synchronous and bounded by configured timeouts. Dataset downloads are limited to metadata-reported and retrieved tables of at most 100,000 rows and 500 columns.
