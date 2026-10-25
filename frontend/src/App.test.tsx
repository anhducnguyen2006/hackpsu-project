import { render, screen, waitFor } from "@testing-library/react";
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

function usePreviewEnv() {
  vi.stubEnv("VITE_API_BASE_URL", "");
  vi.stubEnv("VITE_AUTH0_AUDIENCE", "");
}

it("shows five local stages and never requests data", async () => {
  usePreviewEnv();
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
  usePreviewEnv();
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
  usePreviewEnv();
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

it("keeps the newest analysis when an older file response arrives late", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
  const card = (datasetId: string, title: string, fileName: string) => ({
    dataset_id: datasetId,
    title,
    source: "Zenodo",
    description: "Public table.",
    repository_url: `https://zenodo.org/records/${datasetId}`,
    variables: ["rainfall"],
    instance_count: 10,
    feature_count: 2,
    data_available: true,
    data_status: "available",
    eligibility_status: "supported_resource_verified",
    download_performed: false,
    download_resources: [{ url: "https://zenodo.org/api/records/1/files/data.csv/content", format: "csv", file_id: fileName, filename: fileName, eligible: true }],
    preliminary_relevance_score: null,
    semantic_similarity_score: 0.5,
    score_type: "semantic_similarity",
    relevance_explanation: "Metadata match only.",
    score_confidence: "low",
    concept_matches: [],
    matched_research_variables: [],
    missing_or_unverified_variables: [],
    classification: "partially_relevant",
  });
  const analysis = (title: string, rows: number) => ({
    dataset: { dataset_id: "zenodo:2", title, source: "Zenodo", description: "Parsed file.", repository_url: "https://zenodo.org/records/2", variables: ["storage_ml"], instance_count: rows, feature_count: 1, data_available: true, data_status: "analyzed", preliminary_relevance_score: null, relevance_explanation: "Analysis result.", score_confidence: "low" },
    data_status: "analyzed",
    profile: { row_count: rows, column_count: 1, column_names: ["storage_ml"], duplicate_row_count: 0, columns: [{ name: "storage_ml", data_type: "float64", measurement_type: "numeric", missing_count: 0, missing_fraction: 0, unique_count: 4, is_constant: false, is_near_empty: false, research_roles: [], numeric_summary: { count: rows, mean: 15, median: 14, standard_deviation: 1, minimum: 1, percentile_25: 2, percentile_75: 3, maximum: 4 }, categorical_summary: [] }], research_variable_evidence: [], correlations: [], quality_flags: [] },
    assessment: null,
    ai_assessment_status: "unavailable",
    warnings: [],
    analyzed_resource: { url: "https://zenodo.org/api/records/2/files/data.csv/content", format: "csv", filename: "data.csv", eligible: true },
    download_performed: true,
    history_saved: false,
  });
  let releaseStale: (value: Response) => void = () => {};
  const stale = new Promise<Response>((resolve) => { releaseStale = resolve; });
  const bodies: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/discovery/search")) {
      return Promise.resolve({ ok: true, json: async () => ({ interpretation: { original_research_question: "Does rainfall relate to crop yield?", research_subject: "water", independent_variables: ["month"], dependent_variables: ["storage"], target_population: "reservoirs", synonyms: [], search_terms: ["water", "storage", "month"] }, datasets: [card("zenodo:1", "Rain one", "a.csv"), card("zenodo:2", "Reservoir card", "b.csv")], explanation: "Live repository results.", warnings: [], processing_mode: "gemini", ranking_status: "semantic_embeddings", research_query_id: 44 }) } as Response);
    }
    if (url.endsWith("/discovery/graph")) return Promise.resolve({ ok: true, json: async () => ({ nodes: [], edges: [] }) } as Response);
    bodies.push(String(init?.body));
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer test-token");
    const request = JSON.parse(String(init?.body));
    if (request.dataset_id === "zenodo:1") return stale;
    return Promise.resolve({ ok: true, json: async () => analysis("Reservoir storage", 9) } as Response);
  });
  render(<App authorizedFetch={authorizedFetch} />);
  await userEvent.type(screen.getByRole("textbox", { name: "Research question" }), "Does rainfall relate to crop yield?");
  await userEvent.click(screen.getByRole("button", { name: "Find datasets" }));
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  const analyze = await screen.findAllByRole("button", { name: "Analyze dataset" });
  await userEvent.click(analyze[0]);
  await userEvent.click(screen.getAllByRole("button", { name: "Analyzing…" })[1]);
  expect(await screen.findByText("Reservoir storage")).toBeVisible();
  expect(screen.getByText("9 observed records")).toBeVisible();
  releaseStale({ ok: true, json: async () => analysis("Stale rainfall file", 2) } as Response);
  await waitFor(() => expect(screen.queryByText("Stale rainfall file")).not.toBeInTheDocument());
  expect(screen.getByText("9 observed records")).toBeVisible();
  expect(bodies.every((body) => body.includes("\"research_query_id\":44"))).toBe(true);
  expect(bodies.every((body) => body.includes("Does rainfall relate to crop yield?"))).toBe(true);
  await userEvent.click(screen.getByRole("button", { name: "Datasets" }));
  expect(screen.getByText("Rain one")).toBeVisible();
  expect(screen.getByText("Reservoir card")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Graph" }));
  expect(screen.getByRole("heading", { name: "Graph" })).toBeVisible();
});
