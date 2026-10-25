import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EXAMPLE_INTERPRETATION } from "../demo/researchExample";
import type { ResearchInterpretation } from "../types";
import { InterpretationSheet } from "./InterpretationSheet";

function interpretation(overrides: Partial<ResearchInterpretation> = {}): ResearchInterpretation {
  return {
    ...EXAMPLE_INTERPRETATION,
    ...overrides,
  };
}

it("marks interpreted terms as fallback concepts", () => {
  render(<InterpretationSheet interpretation={EXAMPLE_INTERPRETATION} processingMode="keyword_fallback" />);
  for (const value of ["student academic performance", "study time", "academic performance", "students", "grades", "student", "studytime", "performance"]) {
    expect(screen.getAllByText(value).length).toBeGreaterThan(0);
  }
  expect(screen.getByText("Keyword fallback interpretation")).toBeVisible();
  expect(screen.queryByText("Verified dataset columns")).not.toBeInTheDocument();
});

it.each([
  ["an empty assumptions array", []],
  ["several assumptions", ["The population is observational.", "Geographic scope is unspecified."]],
])("renders safely with %s", (_description, assumptions) => {
  render(
    <InterpretationSheet
      interpretation={interpretation({ assumptions_or_ambiguities: assumptions })}
      processingMode="gemini"
    />,
  );

  expect(screen.getByRole("heading", { name: "Interpretation" })).toBeVisible();
  if (assumptions.length > 0) {
    expect(screen.getByText(assumptions.join(" "))).toBeVisible();
  }
});

it.each([
  ["omitted", {}],
  ["null", { assumptions_or_ambiguities: null }],
])("renders safely when assumptions_or_ambiguities is %s", (_description, overrides) => {
  render(
    <InterpretationSheet
      interpretation={interpretation(overrides as Partial<ResearchInterpretation>)}
      processingMode="gemini"
    />,
  );

  expect(screen.getByRole("heading", { name: "Interpretation" })).toBeVisible();
  expect(screen.queryByText("Ambiguities")).not.toBeInTheDocument();
});
