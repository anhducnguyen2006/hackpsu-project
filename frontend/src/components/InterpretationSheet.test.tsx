import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EXAMPLE_INTERPRETATION } from "../demo/researchExample";
import { InterpretationSheet } from "./InterpretationSheet";

it("marks interpreted terms as fallback concepts", () => {
  render(<InterpretationSheet interpretation={EXAMPLE_INTERPRETATION} processingMode="keyword_fallback" />);
  for (const value of ["student academic performance", "study time", "academic performance", "students", "grades", "student", "studytime", "performance"]) {
    expect(screen.getAllByText(value).length).toBeGreaterThan(0);
  }
  expect(screen.getByText("Keyword fallback interpretation")).toBeVisible();
  expect(screen.queryByText("Verified dataset columns")).not.toBeInTheDocument();
});
