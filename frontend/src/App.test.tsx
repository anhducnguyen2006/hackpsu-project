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

it("walks the cached example through all five stages without requests", async () => {
  const request = vi.spyOn(globalThis, "fetch");
  render(<App />);
  expect(screen.getByRole("heading", { name: /From question to evidence/i })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Explore the example" }));
  for (const name of ["Interpretation", "Datasets", "Graph", "Analysis"]) {
    if (name !== "Interpretation") await userEvent.click(screen.getByRole("button", { name }));
    expect(screen.getByRole("heading", { name })).toBeVisible();
    expect(screen.getByText("Static preview · cached UCI example")).toBeVisible();
    expect(screen.getByText("Cached example question")).toBeVisible();
    expect(screen.getAllByText("How is study time associated with academic performance?").length).toBeGreaterThan(0);
  }
  expect(request).not.toHaveBeenCalled();
});

it("keeps an edited question separate from fixed example results", async () => {
  render(<App />);
  await userEvent.type(screen.getByRole("textbox", { name: "Research question" }), "Does sleep affect memory?");
  await userEvent.click(screen.getByRole("button", { name: "Find datasets" }));
  expect(screen.getByRole("status")).toHaveTextContent("Static preview: live search is not connected");
  expect(screen.queryByRole("heading", { name: "Datasets" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Explore the example" }));
  expect(screen.getAllByText("How is study time associated with academic performance?").length).toBeGreaterThan(0);
  expect(screen.queryByText("Does sleep affect memory?")).not.toBeInTheDocument();
});
