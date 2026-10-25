import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EXAMPLE_ANALYSIS, EXAMPLE_DATASETS, EXAMPLE_INTERPRETATION } from "../demo/researchExample";
import { KnowledgeGraphShell } from "./KnowledgeGraphShell";

it("draws only supported relations and lists every edge", () => {
  const { container } = render(<KnowledgeGraphShell interpretation={EXAMPLE_INTERPRETATION} datasets={EXAMPLE_DATASETS} analysis={EXAMPLE_ANALYSIS} />);
  expect(screen.getByText("No verified publication links are available.")).toBeVisible();
  expect(screen.getByText(/Question → study time/)).toBeVisible();
  expect(screen.getByText(/study time → studytime/)).toBeVisible();
  expect(screen.getAllByText(/Verified UCI codebook mapping: studytime/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/uci:320/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/uci:856/).length).toBeGreaterThan(0);
  expect(container.querySelectorAll("[data-publication-node]")).toHaveLength(0);
  expect(container.querySelectorAll('a[href*="doi.org"]')).toHaveLength(0);
  const edgeIds = Array.from(container.querySelectorAll("svg [data-edge-id]"), (edge) => edge.getAttribute("data-edge-id"));
  const listIds = Array.from(container.querySelectorAll("ol.relation-list [data-relation-id]"), (item) => item.getAttribute("data-relation-id"));
  expect(edgeIds).toEqual(listIds);
});
