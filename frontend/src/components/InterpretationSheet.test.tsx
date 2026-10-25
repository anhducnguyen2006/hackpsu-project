import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { ResearchInterpretation } from "../types";
import { EXAMPLE_INTERPRETATION } from "../demo/researchExample";
import { InterpretationSheet } from "./InterpretationSheet";

function malformed(overrides: Record<string, unknown>): ResearchInterpretation {
  return { ...EXAMPLE_INTERPRETATION, ...overrides } as ResearchInterpretation;
}

it("marks interpreted terms as fallback concepts", () => {
  render(<InterpretationSheet interpretation={EXAMPLE_INTERPRETATION} processingMode="keyword_fallback" />);
  for (const value of ["student academic performance", "study time", "academic performance", "students", "grades", "student", "studytime", "performance"]) {
    expect(screen.getAllByText(value).length).toBeGreaterThan(0);
  }
  expect(screen.getByText("Keyword fallback interpretation")).toBeVisible();
  expect(screen.queryByText("Verified dataset columns")).not.toBeInTheDocument();
  expect(screen.queryByText(/did not match the expected contract/)).not.toBeInTheDocument();
});

it("renders when optional ambiguities are omitted, null, or empty", () => {
  const { assumptions_or_ambiguities: _removed, ...omitted } = EXAMPLE_INTERPRETATION;
  const { unmount } = render(<InterpretationSheet interpretation={omitted as ResearchInterpretation} processingMode="gemini" />);
  expect(screen.getByRole("heading", { name: "Interpretation" })).toBeVisible();
  expect(screen.queryByText("Ambiguities")).not.toBeInTheDocument();
  unmount();
  const nulled = render(<InterpretationSheet interpretation={malformed({ assumptions_or_ambiguities: null })} processingMode="gemini" />);
  expect(screen.getByText("study time")).toBeVisible();
  expect(screen.queryByText("Ambiguities")).not.toBeInTheDocument();
  expect(screen.queryByText(/did not match the expected contract/)).not.toBeInTheDocument();
  nulled.unmount();
  render(<InterpretationSheet interpretation={{ ...EXAMPLE_INTERPRETATION, assumptions_or_ambiguities: [] }} processingMode="gemini" />);
  expect(screen.queryByText("Ambiguities")).not.toBeInTheDocument();
  expect(screen.queryByText(/did not match the expected contract/)).not.toBeInTheDocument();
});

it("shows an empty synonym list as unspecified and a missing list as unavailable", () => {
  const { unmount } = render(<InterpretationSheet interpretation={{ ...EXAMPLE_INTERPRETATION, synonyms: [] }} />);
  expect(screen.getAllByText("Not specified").length).toBeGreaterThan(0);
  expect(screen.queryByText(/did not match the expected contract/)).not.toBeInTheDocument();
  unmount();
  render(<InterpretationSheet interpretation={malformed({ synonyms: null, search_terms: "not-a-list" })} />);
  expect(screen.getByRole("heading", { name: "Interpretation" })).toBeVisible();
  expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
  expect(screen.getByText(/Synonyms were missing/)).toBeVisible();
  expect(screen.getByText(/Search terms were not a list/)).toBeVisible();
  expect(screen.getByText("study time")).toBeVisible();
  expect(screen.queryByText("not-a-list")).not.toBeInTheDocument();
});

it("shows populated ambiguities exactly", () => {
  render(<InterpretationSheet interpretation={{ ...EXAMPLE_INTERPRETATION, assumptions_or_ambiguities: ["Pollution type is unspecified."] }} />);
  expect(screen.getByText("Pollution type is unspecified.")).toBeVisible();
});
