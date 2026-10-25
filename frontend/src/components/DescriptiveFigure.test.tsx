import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { EXAMPLE_EXPLORATION } from "../demo/researchExample";
import { DescriptiveFigure } from "./DescriptiveFigure";

it("pairs a descriptive SVG with equivalent cached group data", () => {
  render(<DescriptiveFigure exploration={EXAMPLE_EXPLORATION} />);
  const table = screen.getByRole("table", { name: /grouped descriptive data/i });
  for (const [category, count] of [["1", "212"], ["2", "305"], ["3", "97"], ["4", "35"]]) {
    const row = within(table).getByRole("row", { name: new RegExp(`^${category} ${count}`) });
    expect(row).toBeVisible();
  }
  expect(screen.getByRole("img", { name: /mean final grade by studytime category/i })).toBeVisible();
  expect(screen.getByText("649 analyzed observations")).toBeVisible();
  expect(screen.getByText("0 excluded")).toBeVisible();
  expect(screen.getByText(/do not establish causation or statistical significance/i)).toBeVisible();
  expect(screen.queryByText(/p-value/i)).not.toBeInTheDocument();
});
