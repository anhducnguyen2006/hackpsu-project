# API Reference

Last verified: 2026-10-25

Base URL: `http://localhost:8000/api/v1`. Protected routes require an Auth0 access token: `Authorization: Bearer <access_token>`. The token must be an RS256 JWT for `AUTH0_AUDIENCE`, issued by `https://AUTH0_DOMAIN/`. ID tokens and identities sent in JSON or custom headers are ignored. CORS is configured from `BACKEND_CORS_ORIGINS` and allows the `Authorization` header.

`GET /health` is public. Missing or invalid tokens return `401`. A valid token without a configured required scope returns `403`. Missing Auth0 configuration, a disconnected TigerData database, and a database that has not had `004_research_query_owner.sql` applied return `503`. Those storage failures are not authentication failures. `429` means the process-local per-user limit was reached. See `docs/AUTHENTICATION.md`.

## `GET /health`

Returns process health.

Response `200`:

```json
{"status": "ok"}
```

## `POST /discovery/search`

Searches verified repository metadata for a natural-language research question. Gemini interprets the question when available; normal candidate ranking uses local embedding similarity across the full question and independently extracted research concepts. If Gemini is unavailable, deterministic concept extraction remains explicit in `processing_mode` and `warnings`.

Each result may include additive `concept_matches` evidence. Normal results include only records whose provider metadata verifies a supported public CSV, TSV, or TAB resource, or a UCI dataset with a native retrieval path. `eligibility_status` of `supported_resource_verified` means the file list was checked. `download_verified` is not used during search. `download_performed` stays false. Semantic scores are cosine similarity over verified metadata, not probabilities or scientific-suitability scores. Scores below `0.20` are omitted rather than used to fill `limit`. Concept scores are fused as full question (0.45), independent variables (0.25), dependent variables (0.20), and context/subject/synonyms/search terms (0.10); unavailable groups are renormalized so datasets matching only one research variable remain eligible.

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

Errors include `401` before any repository or Gemini work, `422` for invalid request validation, `429` for the process-local discovery limit, and `503` when authentication is not configured. Repository failure is returned as an empty result with a warning; the route does not fabricate records. A failed history write is logged and is not described as saved.

### DEMO_MODE

With `DEMO_MODE=true`, this route returns cached verified metadata for UCI #320 and #856 for education-related questions. It does not perform a live UCI search or claim live Gemini generation. Unmatched questions return no cached records.

## `POST /datasets/resources`

Re-reads provider metadata for one dataset id. The id is in the JSON body because Dataverse persistent ids contain slashes. The response lists supported public files in `resources`. Files with a tabular filename but missing or `text/plain` type metadata are returned separately in `verification_candidates` and are not treated as already analyzable. UCI returns no file URL; analysis uses the native retrieval path.

```json
{"dataset_id": "dataverse:doi:10.7910/DVN/EXAMPLE"}
```

## `POST /datasets/analyze`

Retrieves and profiles one dataset. UCI ids use the existing native loader. Dataverse and Zenodo ids are resolved again from published metadata. The server builds the download URL from the provider file id or Zenodo file key. A client-supplied URL is rejected.

When a dataset has one supported file, `resource_id` may be omitted. When it has several, `resource_id` is required. A file is `download_verified` only after its bytes parse as a table. HTML, PDF, archives, and other binary payloads are rejected even if the name ends in `.csv`.

```json
{
  "dataset_id": "zenodo:42",
  "research_question": "How does rainfall affect crop yield?",
  "resource_id": "data.csv"
}
```

The response adds `analyzed_resource`, `eligibility_status`, and `download_performed`. `final_score` is the Python suitability score from Gemini's criteria, not the discovery cosine. A database outage does not discard the computed profile; the warning says the profile was not cached.

## `POST /datasets/{dataset_id}/analyze`

Analyzes a verified UCI dataset. `dataset_id` must use `uci:<positive integer>`. This path remains for UCI clients. External ids should use `POST /datasets/analyze`.

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

- `401` before metadata retrieval or Gemini assessment
- `400` for malformed or non-UCI dataset IDs
- `502` for UCI repository failures
- `422` for invalid request bodies
- `429` for the process-local analysis limit
- `503` when authentication is not configured

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
  "independent_measurement_type": "ordinal_or_encoded_numeric",
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

`GET /dev/dataset-test` is disabled unless `DEV_ROUTES_ENABLED=true`. Even then it requires an access token before it retrieves UCI #320. It is not a general discovery endpoint.

## Research history

`GET /research/history`, `GET /research/{query_id}`, `GET /research/{query_id}/session`, and `POST /research/similar` require an access token. Results are limited to rows whose `user_sub` equals the verified `sub`. Another user's id returns `404`. Similarity search uses the same owner filter. `GET /health/database` also requires a token and returns `503` when TigerData is disconnected, without echoing the connection string.

## Operational limitations

There is no pagination, persistent job system, streaming response, or background worker. External calls are synchronous and bounded by configured timeouts. Dataset downloads are limited to metadata-reported and retrieved tables of at most 100,000 rows and 500 columns. Request limits are process-local.
