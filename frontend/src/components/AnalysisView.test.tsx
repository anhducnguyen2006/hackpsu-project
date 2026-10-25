import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EXAMPLE_ANALYSIS } from "../demo/researchExample";
import { AnalysisView } from "./AnalysisView";

it("shows cached computed values without a fabricated suitability score", () => {
  render(<AnalysisView analysis={EXAMPLE_ANALYSIS} />);
  for (const value of ["649 observed records", "33 columns", "0 duplicate rows", "Computed profile", "studytime", "G3", "1: 212", "2: 305", "3: 97", "4: 35", "11.91", "12"]) {
    expect(screen.getAllByText(value).length).toBeGreaterThan(0);
  }
  expect(screen.getByText(/two cached variable profiles of 33 total columns/i)).toBeVisible();
  expect(screen.getByText("ordinal")).toBeVisible();
  expect(screen.getByText("weekly study time")).toBeVisible();
  expect(screen.getAllByText("Unavailable")).toHaveLength(7);
  expect(screen.getByText(/do not establish causation/i)).toBeVisible();
  expect(screen.queryByText(/suitability.*\/100/i)).not.toBeInTheDocument();
});
