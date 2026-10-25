#!/usr/bin/env python3
"""Measure Gemini connectivity and structured interpretation latency.

Run this script from a normal macOS terminal, outside the Codex network
sandbox, with the backend virtual environment active or selected explicitly:

    cd backend
    PYTHONPATH=. ../.venv/bin/python scripts/diagnose_gemini.py

The script prints no API keys, exception messages, prompts, or response bodies.
Each request uses a fresh client with retries disabled so timings are directly
comparable.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from typing import Any

from app.api.schemas import ResearchInterpretation
from app.config import settings


QUESTION = "Does air pollution affect asthma hospitalization rates among adults in urban areas?"


@dataclass(frozen=True)
class DiagnosticConfig:
    name: str
    model: str
    timeout_ms: int
    thinking_level: str | None = None


CONFIGURATIONS = (
    DiagnosticConfig("A", "gemini-3.8-flash", 15_000, "LOW"),
    DiagnosticConfig("B", "gemini-3.8-flash", 45_000, "LOW"),
    # Omit thinking_config so Gemini 2.5 uses its supported model default.
    DiagnosticConfig("C", "gemini-2.5-flash", 30_000),
)


def _minimal_prompt() -> str:
    return "Reply with exactly: OK"


def _structured_prompt() -> str:
    return (
        "Interpret this scientific research question for dataset discovery and "
        "return only the structured fields in the response schema. Preserve the "
        "researcher's intent. Identify independent and dependent variables only "
        "when applicable. Identify population and geography only when supplied. "
        "Include useful scientific synonyms and repository search terms. Do not "
        "invent datasets, source names, IDs, URLs, statistics, or findings.\n\n"
        f"Research question: {QUESTION}"
    )


def _config(types: Any, diagnostic: DiagnosticConfig, schema: Any | None = None) -> Any:
    values: dict[str, Any] = {
        "max_output_tokens": 32 if schema is None else 900,
    }
    if schema is not None:
        values.update(
            response_mime_type="application/json",
            response_schema=schema,
        )
    if diagnostic.thinking_level is not None:
        thinking_levels = getattr(types, "ThinkingLevel", None)
        level = getattr(thinking_levels, diagnostic.thinking_level, None)
        if level is None:
            raise RuntimeError("The installed SDK does not support the requested thinking level.")
        values["thinking_config"] = types.ThinkingConfig(thinking_level=level)
    return types.GenerateContentConfig(**values)


def _http_status(error: BaseException | None) -> int | str:
    if error is None:
        return 200
    for candidate in (error, getattr(error, "response", None)):
        status = getattr(candidate, "status_code", None)
        if isinstance(status, int):
            return status
        code = getattr(candidate, "code", None)
        if isinstance(code, int):
            return code
    return "unknown"


def _cause_chain(error: BaseException) -> str:
    names: list[str] = []
    current: BaseException | None = error
    while current is not None and len(names) < 8:
        names.append(type(current).__name__)
        current = current.__cause__
    return " -> ".join(names)


def _run_request(diagnostic: DiagnosticConfig, phase: str) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    started = time.perf_counter()
    error: BaseException | None = None
    try:
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=diagnostic.timeout_ms,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        if phase == "minimal":
            response = client.models.generate_content(
                model=diagnostic.model,
                contents=_minimal_prompt(),
                config=_config(types, diagnostic),
            )
            if not getattr(response, "text", None):
                raise ValueError("empty minimal response")
        else:
            response = client.models.generate_content(
                model=diagnostic.model,
                contents=_structured_prompt(),
                config=_config(types, diagnostic, ResearchInterpretation),
            )
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                ResearchInterpretation.model_validate(parsed)
            else:
                text = getattr(response, "text", None)
                if not text:
                    raise ValueError("empty structured response")
                ResearchInterpretation.model_validate_json(text)
    except BaseException as caught:  # Diagnostic output must remain sanitized.
        error = caught

    result = {
        "config": diagnostic.name,
        "phase": phase,
        "model": diagnostic.model,
        "timeout_seconds": diagnostic.timeout_ms / 1000,
        "thinking": diagnostic.thinking_level or "model_default",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "http_status": _http_status(error),
        "result": "failure" if error else "success",
        "exception_type": type(error).__name__ if error else "-",
        "cause_chain": _cause_chain(error) if error else "-",
    }
    print(
        "RESULT "
        + " ".join(f"{key}={value!r}" for key, value in result.items())
    )
    return result


def _print_comparison(results: list[dict[str, Any]]) -> None:
    print("\nCOMPARISON")
    print("| Config | Model | Timeout | Thinking | Phase | Result | Time (s) | HTTP | Exception |")
    print("|---|---|---:|---|---|---|---:|---:|---|")
    for item in results:
        print(
            "| {config} | {model} | {timeout_seconds:.0f} | {thinking} | {phase} | "
            "{result} | {elapsed_seconds:.3f} | {http_status} | {exception_type} |".format(
                **item
            )
        )

    print("\nSUMMARY")
    for config in (item["config"] for item in results[::2]):
        structured = [
            item["elapsed_seconds"]
            for item in results
            if item["config"] == config
            and item["phase"] == "structured"
            and item["result"] == "success"
        ]
        if structured:
            print(f"config={config} structured_median_seconds={statistics.median(structured):.3f}")
        else:
            print(f"config={config} structured_median_seconds=unavailable")


def main() -> int:
    if not settings.gemini_api_key:
        print("ERROR missing GEMINI_API_KEY; no request was sent")
        return 2

    print("Gemini diagnostic: retries disabled; credentials and response bodies are hidden")
    print(f"Question: {QUESTION}")
    results: list[dict[str, Any]] = []
    for diagnostic in CONFIGURATIONS:
        results.append(_run_request(diagnostic, "minimal"))
        results.append(_run_request(diagnostic, "structured"))
    _print_comparison(results)
    return 0 if all(item["result"] == "success" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
