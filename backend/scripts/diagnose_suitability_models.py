"""Bounded live comparison of Gemini suitability models.

Run from backend with at most one request per model by default:

    PYTHONPATH=. ../.venv/bin/python scripts/diagnose_suitability_models.py \
        --models gemini-3.8-flash gemini-2.5-flash

The script fetches UCI #320 once, profiles it deterministically, and sends the
same verified evidence and ResearchAssessment schema to each selected model.
It prints only timing, validation, score-null counts, and sanitized error labels.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from google import genai
from google.genai import types

from app.assessment.gemini import GeminiService, GeminiUnavailableError, _failure_label
from app.assessment.suitability import calculate_final_score
from app.api.schemas import ResearchAssessment
from app.config import settings
from app.discovery.search import DiscoveryService
from app.discovery.uci import UCIRepositoryService
from app.profiling.profiler import DataProfiler


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        nargs="+",
        default=[settings.gemini_model, "gemini-2.5-flash"],
        help="Models to compare; one live suitability call is made per model.",
    )
    parser.add_argument("--dataset-id", type=int, default=320)
    parser.add_argument("--timeout-ms", type=int, default=settings.gemini_request_timeout_ms)
    return parser.parse_args()


def _fixture(dataset_id: int):
    repository = UCIRepositoryService()
    source_record, dataframe, source_metadata = repository.fetch_dataset(dataset_id)
    interpretation = DiscoveryService._fallback_interpretation(
        "Does weekly study time affect final academic performance among students?"
    )
    profile = DataProfiler().profile(
        dataframe,
        interpretation,
        source_record.variable_descriptions,
        source_record.variable_types,
    )
    return source_record, dataframe, source_metadata, interpretation, profile


def _run_model(
    model: str,
    source_record: Any,
    interpretation: Any,
    profile: Any,
    timeout_ms: int,
) -> dict[str, Any]:
    previous_model = settings.gemini_model
    previous_timeout = settings.gemini_request_timeout_ms
    previous_fallback = settings.gemini_fallback_model
    settings.gemini_model = model
    settings.gemini_request_timeout_ms = timeout_ms
    settings.gemini_fallback_model = None
    started = time.perf_counter()
    try:
        generated = GeminiService().assess_suitability(
            "Does weekly study time affect final academic performance among students?",
            interpretation,
            source_record,
            profile,
        )
        assessment = calculate_final_score(ResearchAssessment.model_validate(generated))
        scores = [
            getattr(assessment.criteria, name).score
            for name in (
                "research_question_and_outcome_alignment",
                "required_variable_coverage",
                "sample_size_considerations",
                "data_quality_and_completeness",
                "documentation_and_provenance",
                "population_and_temporal_relevance",
            )
        ]
        return {
            "model": model,
            "status": "success",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "configured_timeout_ms": timeout_ms,
            "retry_attempts": 1,
            "schema_valid": True,
            "criterion_count": len(scores),
            "null_criterion_count": sum(score is None for score in scores),
            "final_score": assessment.final_score,
        }
    except GeminiUnavailableError as error:
        return {
            "model": model,
            "status": "error",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "configured_timeout_ms": timeout_ms,
            "retry_attempts": 1,
            "schema_valid": False,
            "error_category": _failure_label(error),
            "original_exception_type": error.original_exception_type,
            "http_status": error.http_status,
            "cause_chain": error.cause_chain,
            "error_summary": error.error_summary,
        }
    except Exception as error:
        return {
            "model": model,
            "status": "error",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "configured_timeout_ms": timeout_ms,
            "retry_attempts": 1,
            "schema_valid": False,
            "error_category": _failure_label(error),
            "original_exception_type": type(error).__name__,
            "http_status": None,
            "cause_chain": [type(error).__name__],
        }
    finally:
        settings.gemini_model = previous_model
        settings.gemini_request_timeout_ms = previous_timeout
        settings.gemini_fallback_model = previous_fallback


def _client(model: str, timeout_ms: int):
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=1, http_status_codes=[]),
        ),
    )


def _run_text_probe(model: str, timeout_ms: int) -> dict[str, Any]:
    started = time.perf_counter()
    client = None
    try:
        client = _client(model, timeout_ms)
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly OK.",
            config=types.GenerateContentConfig(max_output_tokens=8),
        )
        text = getattr(response, "text", None)
        return {
            "model": model,
            "status": "success" if text else "empty_response",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "configured_timeout_ms": timeout_ms,
            "retry_attempts": 1,
            "response_text_present": bool(text),
        }
    except Exception as error:
        from app.assessment.gemini import _cause_chain, _http_status, _safe_error_summary

        return {
            "model": model,
            "status": "error",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "configured_timeout_ms": timeout_ms,
            "retry_attempts": 1,
            "error_category": _failure_label(error),
            "original_exception_type": type(error).__name__,
            "http_status": _http_status(error),
            "cause_chain": _cause_chain(error),
            "error_summary": _safe_error_summary(error),
        }
    finally:
        if client is not None:
            close = getattr(client, "close", None)
            if callable(close):
                close()


def main() -> None:
    args = _args()
    fixture_started = time.perf_counter()
    source_record, dataframe, source_metadata, interpretation, profile = _fixture(
        args.dataset_id
    )
    text_results = [_run_text_probe(model, args.timeout_ms) for model in args.models]
    structured_results = []
    for text_result, model in zip(text_results, args.models):
        if text_result["status"] == "success":
            structured_results.append(
                _run_model(model, source_record, interpretation, profile, args.timeout_ms)
            )
    print(
        json.dumps(
            {
                "dataset_id": source_record.dataset_id,
                "rows": len(dataframe),
                "columns": len(dataframe.columns),
                "fixture_profile_version": DataProfiler.PROFILER_VERSION,
                "fixture_setup_elapsed_ms": round(
                    (time.perf_counter() - fixture_started) * 1000, 1
                ),
                "models_tested": len(args.models),
                "plain_text_results": text_results,
                "structured_results": structured_results,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
