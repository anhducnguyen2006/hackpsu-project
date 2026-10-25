import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => vi.restoreAllMocks());

it("shows five local stages and never requests data", async () => {
  const request = vi.spyOn(globalThis, "fetch");
  render(<App />);
  expect(screen.getByText("DataOPedia")).toBeVisible();
  expect(screen.getByText("Static preview · cached UCI example")).toBeVisible();
  for (const name of ["Question", "Interpretation", "Datasets", "Graph", "Analysis"]) {
    expect(screen.getByRole("button", { name })).toBeVisible();
  }
  await userEvent.click(screen.getByRole("button", { name: "Graph" }));
  expect(screen.getByRole("heading", { name: "Graph" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Datasets" })).not.toBeInTheDocument();
  expect(request).not.toHaveBeenCalled();
});
