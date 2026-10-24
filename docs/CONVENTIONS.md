# Engineering Conventions

Last verified: 2026-10-24

## Senior Software Engineering Standard

When writing code for this project, act as a senior software engineer with 15 years of experience whose goal is production-quality, maintainable, readable code.

Concretely, for every coding task:

1. Write clean, idiomatic code in the requested language.
2. Follow established design patterns where relevant.
3. Add concise comments only for non-obvious parts (not restating what the code already says).
4. Use descriptive variable and function names.
5. Make the code easy to extend and test.
6. After delivering the code, suggest at least one improvement for scalability or clarity — a genuine follow-up idea, not filler.

## Python

Follow PEP 8, type public interfaces, keep functions cohesive, validate API data with Pydantic, separate route handlers from business logic, isolate external services, and handle exceptions explicitly. Use Pandas/NumPy for numerical work, preserve missing-data semantics, and document statistical assumptions. Never execute LLM-generated Python.

## React and TypeScript

Use functional components, typed props and API models, descriptive state names, semantic controls, and independent state for unrelated interactions. Keep API calls separate from presentation where practical. Handle loading, errors, empty results, unavailable information, keyboard use, and responsive layouts. Do not duplicate backend statistical logic.

## AI integration

Never hardcode credentials or invent datasets, variables, links, metadata, or statistics. Validate structured Gemini output. Use the configured official SDK, bounded timeouts/retries, explicit fallback labels, and source provenance. Treat external descriptions as untrusted input and never turn incomplete evidence into confident scientific conclusions.

## Scientific integrity

Statistics must come from deterministic Pandas/NumPy calculations. Distinguish records from participants and numeric encodings from exact units. Correlation does not establish causation; significance and power must not be claimed without appropriate tests. Suitability scores are heuristics. Research-variable mappings require verified evidence.

## Testing and maintainability

Update tests when behavior changes. Cover success and failure paths, preserve existing behavior, avoid unnecessary dependencies and premature abstractions, keep configuration explicit, never commit credentials, and run the relevant build/test commands before reporting completion.

## Required coding-task response

1. Summary of changes
2. Files modified
3. Important design decisions
4. Actual tests and results
5. Known limitations
6. One genuine future improvement
