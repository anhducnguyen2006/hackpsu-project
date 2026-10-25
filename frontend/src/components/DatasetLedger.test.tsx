import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { EXAMPLE_DATASETS } from "../demo/researchExample";
import { DatasetLedger } from "./DatasetLedger";

it("shows documented UCI metadata and gates the analyzed example", async () => {
  const onOpenAnalysis = vi.fn();
  render(<DatasetLedger datasets={EXAMPLE_DATASETS} onOpenAnalysis={onOpenAnalysis} />);
  expect(screen.getByText("Student Performance")).toBeVisible();
  expect(screen.getByText("Higher Education Students Performance Evaluation")).toBeVisible();
  expect(screen.getByText("uci:320")).toBeVisible();
  expect(screen.getByText("uci:856")).toBeVisible();
  expect(screen.getByText("649")).toBeVisible();
  expect(screen.getByText("145")).toBeVisible();
  expect(screen.getByText("92")).toBeVisible();
  expect(screen.getByText("48")).toBeVisible();
  expect(screen.getByText(/Cached verified UCI metadata matched study time/)).toBeVisible();
  expect(screen.getByText(/Directly comparable study-time coding/)).toBeVisible();
  expect(screen.getByText(/Confidence: high/)).toBeVisible();
  expect(screen.getByText(/Confidence: low/)).toBeVisible();
  expect(screen.getAllByRole("link", { name: "UCI source" })).toHaveLength(2);
  await userEvent.click(screen.getByRole("button", { name: "Details for Student Performance" }));
  expect(screen.getByText("weekly study time")).toBeVisible();
  expect(screen.getByText(EXAMPLE_DATASETS[0].repository_url)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Open analysis preview" }));
  expect(onOpenAnalysis).toHaveBeenCalledWith("uci:320");
  expect(screen.getByRole("button", { name: "Analysis preview unavailable" })).toBeDisabled();
});

it("does not replace null metadata or relevance with zero", () => {
  const sparse = { ...EXAMPLE_DATASETS[1], instance_count: null, feature_count: null, preliminary_relevance_score: null };
  render(<DatasetLedger datasets={[sparse]} onOpenAnalysis={() => {}} />);
  const row = screen.getByRole("article");
  expect(within(row).getByText("Unavailable")).toBeVisible();
  expect(within(row).getAllByText("Not documented")).toHaveLength(2);
  expect(within(row).queryByText("0")).not.toBeInTheDocument();
});
