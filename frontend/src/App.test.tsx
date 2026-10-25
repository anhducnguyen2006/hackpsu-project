import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import type { AuthorizedFetch } from "./auth/api";
import App from "./App";

const authorizedFetch: AuthorizedFetch = (input, init) => {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", "Bearer test-token");
  return fetch(input, { ...init, headers });
};

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllEnvs(); });

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

it("renders the live interpretation and discovery response", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
  const request = vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({
      interpretation: {
        original_research_question: "Does rainfall relate to crop yield?",
        research_subject: "crop yield",
        independent_variables: ["rainfall"],
        dependent_variables: ["crop yield"],
        target_population: "farms",
        synonyms: ["precipitation"],
        search_terms: ["rainfall", "crop", "yield"],
      },
      datasets: [{
        dataset_id: "uci:999",
        title: "Live Crop Dataset",
        source: "UCI Machine Learning Repository",
        description: "Verified crop metadata.",
        repository_url: "https://archive.ics.uci.edu/dataset/999",
        variables: ["rainfall", "yield"],
        instance_count: 100,
        feature_count: 2,
        data_available: true,
        data_status: "available",
        eligibility_status: "supported_resource_verified",
        eligibility_reason: "UCI native retrieval path is available.",
        download_performed: false,
        preliminary_relevance_score: null,
        semantic_similarity_score: 0.88,
        score_type: "semantic_similarity",
        relevance_explanation: "Verified metadata matched rainfall and yield.",
        score_confidence: "high",
        concept_matches: [],
        matched_research_variables: ["rainfall", "crop yield"],
        missing_or_unverified_variables: [],
        classification: "relevant",
      }],
      explanation: "Live repository results.",
      warnings: [],
      processing_mode: "gemini",
      ranking_status: "semantic_embeddings",
    }),
  } as Response);
  render(<App authorizedFetch={authorizedFetch} />);
  await userEvent.type(screen.getByRole("textbox", { name: "Research question" }), "Does rainfall relate to crop yield?");
  await userEvent.click(screen.getByRole("button", { name: "Find datasets" }));

  expect(await screen.findByText("AI interpretation")).toBeVisible();
  expect(screen.getAllByText("crop yield").length).toBeGreaterThan(0);
  expect(screen.getByText("Live repository search")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Datasets" }));
  expect(await screen.findByText("Live Crop Dataset")).toBeVisible();
  expect(screen.getByText("0.88")).toBeVisible();
  expect(screen.getByText("Cosine similarity, not a probability or suitability score")).toBeVisible();
  expect(screen.getByText("supported resource verified; not downloaded")).toBeVisible();
  expect(request).toHaveBeenCalledWith("http://localhost:8000/api/v1/discovery/search", expect.objectContaining({
    method: "POST",
    body: JSON.stringify({ research_question: "Does rainfall relate to crop yield?", limit: 12 }),
  }));
  const searchCall = request.mock.calls.find((call) => String(call[0]).endsWith("/discovery/search"));
  const graphCall = request.mock.calls.find((call) => String(call[0]).endsWith("/discovery/graph"));
  expect(new Headers(searchCall?.[1]?.headers).get("Authorization")).toBe("Bearer test-token");
  expect(new Headers(graphCall?.[1]?.headers).get("Authorization")).toBe("Bearer test-token");
});

it("keeps the application visible when a live interpretation array is malformed", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({
      interpretation: {
        original_research_question: "Does rainfall relate to crop yield?",
        research_subject: "crop yield",
        independent_variables: ["rainfall"],
        dependent_variables: null,
        target_population: "farms",
        synonyms: ["precipitation"],
        assumptions_or_ambiguities: null,
        search_terms: ["rainfall", "crop", "yield"],
      },
      datasets: [],
      explanation: "Live repository results.",
      warnings: [],
      processing_mode: "gemini",
      ranking_status: "semantic_embeddings",
    }),
  } as Response);
  render(<App authorizedFetch={authorizedFetch} />);
  await userEvent.type(screen.getByRole("textbox", { name: "Research question" }), "Does rainfall relate to crop yield?");
  await userEvent.click(screen.getByRole("button", { name: "Find datasets" }));
  expect(await screen.findByRole("heading", { name: "Interpretation" })).toBeVisible();
  expect(screen.getByText("DataOPedia")).toBeVisible();
  expect(screen.getAllByText("rainfall").length).toBeGreaterThan(0);
  expect(screen.getByText(/Outcome variables were missing/)).toBeVisible();
  expect(screen.queryByText(/did not match the expected contract/)).toBeVisible();
});
