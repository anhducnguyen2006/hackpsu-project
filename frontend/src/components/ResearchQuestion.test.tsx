import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { ResearchQuestion } from "./ResearchQuestion";

it("keeps a new question separate from the cached example", async () => {
  const onExploreExample = vi.fn();
  render(<ResearchQuestion exampleQuestion="How is study time associated with academic performance?" onExploreExample={onExploreExample} />);
  const input = screen.getByRole("textbox", { name: "Research question" });
  await userEvent.type(input, "A different question");
  expect(input).toHaveValue("A different question");
  await userEvent.click(screen.getByRole("button", { name: "Find datasets" }));
  expect(screen.getByText("Static preview: live search is not connected")).toBeVisible();
  expect(onExploreExample).not.toHaveBeenCalled();
  expect(screen.getByText("Illustrative workflow")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Explore the example" }));
  expect(onExploreExample).toHaveBeenCalledOnce();
});
