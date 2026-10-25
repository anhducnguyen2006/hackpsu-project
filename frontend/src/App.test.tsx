import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";
import {
  CROP_QUESTION,
  dataverseDataset,
  discoveryResponse,
  graphResponse,
  pdfOnlyDataset,
  resourceListing,
  sourceAnalysis,
  uciAnalysis,
  uciCropDataset,
  zenodoDataset,
} from "./test/fixtures";

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
        assumptions_or_ambiguities: [],
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
        data_available: true,
        data_status: "available",
        preliminary_relevance_score: null,
        semantic_similarity_score: 0.88,
        score_type: "semantic_similarity",
        relevance_explanation: "Verified metadata matched rainfall and yield.",
        score_confidence: "high",
        concept_matches: [],
        matched_research_variables: ["rainfall", "crop yield"],
        missing_or_unverified_variables: [],
        classification: "relevant",
        analysis_eligibility: "supported_resource_verified",
      }],
      explanation: "Live repository results.",
      warnings: [],
      processing_mode: "gemini",
      ranking_status: "semantic_embeddings",
    }),
  } as Response);
  render(<App />);
  await userEvent.type(screen.getByRole("textbox", { name: "Research question" }), "Does rainfall relate to crop yield?");
  await userEvent.click(screen.getByRole("button", { name: "Find datasets" }));

  expect(await screen.findByText("AI interpretation")).toBeVisible();
  expect(screen.getAllByText("crop yield").length).toBeGreaterThan(0);
  expect(screen.getByText("Live repository search")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Datasets" }));
  expect(await screen.findByText("Live Crop Dataset")).toBeVisible();
  expect(request).toHaveBeenCalledWith("http://localhost:8000/api/v1/discovery/search", expect.objectContaining({
    method: "POST",
    body: JSON.stringify({ research_question: "Does rainfall relate to crop yield?", limit: 12 }),
  }));
});

function jsonResponse(payload: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => payload } as Response;
}

function mockBackend(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8000");
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    return Promise.resolve(handler(String(input), init));
  });
}

async function submitQuestion(question = CROP_QUESTION) {
  render(<App />);
  await userEvent.type(screen.getByRole("textbox", { name: "Research question" }), question);
  await userEvent.click(screen.getByRole("button", { name: "Find datasets" }));
}

it("documents keyword fallback interpretation when Gemini is unavailable", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([uciCropDataset()], "keyword_fallback"));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  expect(await screen.findByText("Keyword fallback interpretation")).toBeVisible();
});

it("renders verified UCI, Dataverse, and Zenodo candidates together", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([uciCropDataset(), dataverseDataset(), zenodoDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  expect(screen.getByText("Live Crop Dataset")).toBeVisible();
  expect(screen.getByText("Rainfall Dataverse")).toBeVisible();
  expect(screen.getByText("Zenodo Yield Tables")).toBeVisible();
  expect(screen.getByText("doi:10.5072/FK2/ABC")).toBeVisible();
  expect(screen.getByText("10.5281/zenodo.123")).toBeVisible();
  expect(screen.getAllByText("Supported data file verified in repository metadata").length).toBeGreaterThan(0);
  expect(screen.queryByText("88.0%")).not.toBeInTheDocument();
  expect(screen.getByText("0.880")).toBeVisible();
  expect(screen.getAllByText(/not a probability or accuracy percentage/i).length).toBeGreaterThan(0);
});

it("opens the knowledge graph without losing discovery results", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([uciCropDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Graph" }));
  expect(screen.getByRole("heading", { name: "Graph" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Datasets" }));
  expect(screen.getByText("Live Crop Dataset")).toBeVisible();
});

it("runs legacy UCI analysis from a live discovery result", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([uciCropDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/uci%3A999/analyze") || url.includes("/datasets/uci:999/analyze")) return jsonResponse(uciAnalysis());
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "Analyze UCI dataset" }));
  expect(await screen.findByText("2 observed records")).toBeVisible();
  expect(screen.getByText("Computed live profile")).toBeVisible();
});

it("lists a single Dataverse file and analyzes it after an explicit action", async () => {
  const dataset = dataverseDataset();
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataset]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(dataset.dataset_id, [{ id: "dataverse-file:11", filename: "observations.csv", format: "csv", size: 20, version: "2" }]));
    if (url.includes("/datasets/source-analyze")) return jsonResponse(sourceAnalysis(dataset.dataset_id, "dataverse-file:11", "observations.csv"));
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  expect(await screen.findByText("observations.csv")).toBeVisible();
  expect(screen.getByText(/CSV · 20 B · version 2/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Analyze selected file" }));
  expect(await screen.findByText("observations.csv")).toBeVisible();
  expect(screen.getByText("Gemini suitability assessment")).toBeVisible();
  expect(screen.getByText("Heuristic suitability (Python-computed)")).toBeVisible();
  expect(screen.getByText("57")).toBeVisible();
});

it("lists Zenodo files and requires an explicit choice when several are eligible", async () => {
  const dataset = zenodoDataset();
  const request = mockBackend((url, init) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataset]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(dataset.dataset_id, [
      { id: "zenodo-file:observations.csv", filename: "observations.csv", format: "csv" },
      { id: "zenodo-file:extra.tsv", filename: "extra.tsv", format: "tsv" },
    ]));
    if (url.includes("/datasets/source-analyze")) {
      const body = JSON.parse(String(init?.body ?? "{}")) as { resource_id?: string };
      if (body.resource_id !== "zenodo-file:extra.tsv") return jsonResponse({ detail: "The selected resource does not belong to this dataset or is not eligible." }, false, 400);
      return jsonResponse(sourceAnalysis(dataset.dataset_id, "zenodo-file:extra.tsv", "extra.tsv", { ai: false }));
    }
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  expect(await screen.findByText("observations.csv")).toBeVisible();
  expect(screen.getByText("extra.tsv")).toBeVisible();
  expect(screen.getByRole("button", { name: "Analyze selected file" })).toBeDisabled();
  await userEvent.click(screen.getByRole("radio", { name: /extra\.tsv/i }));
  await userEvent.click(screen.getByRole("button", { name: "Analyze selected file" }));
  expect(await screen.findByText("AI assessment unavailable")).toBeVisible();
  expect(screen.getByText("2 observed records")).toBeVisible();
  expect(request).toHaveBeenCalledWith("http://localhost:8000/api/v1/datasets/source-analyze", expect.objectContaining({
    body: JSON.stringify({
      dataset_id: dataset.dataset_id,
      resource_id: "zenodo-file:extra.tsv",
      research_question: CROP_QUESTION,
    }),
  }));
});

it("does not present PDF-only records as analyzable datasets", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([pdfOnlyDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  expect(screen.getByRole("heading", { name: "No eligible datasets found" })).toBeVisible();
  expect(screen.queryByText("Methods Paper PDF")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "List eligible files" })).not.toBeInTheDocument();
});

it("keeps a CSV-plus-PDF Dataverse record analyzable from the verified table", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataverseDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(dataverseDataset().dataset_id, [{ id: "dataverse-file:11", filename: "observations.csv", format: "csv" }]));
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  expect(screen.getByText("Rainfall Dataverse")).toBeVisible();
  expect(screen.getByText("csv, pdf")).toBeVisible();
  expect(screen.getByText("Supported data file verified in repository metadata")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  expect(await screen.findByText("observations.csv")).toBeVisible();
  expect(screen.queryByText("notes.pdf")).not.toBeInTheDocument();
});

it("labels metadata verification separately from completed analysis", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataverseDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(dataverseDataset().dataset_id, [{ id: "dataverse-file:11", filename: "observations.csv", format: "csv" }]));
    if (url.includes("/datasets/source-analyze")) return jsonResponse(sourceAnalysis(dataverseDataset().dataset_id, "dataverse-file:11", "observations.csv"));
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  expect(screen.getByText("Supported data file verified in repository metadata")).toBeVisible();
  expect(screen.queryByText("Analysis completed")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  await userEvent.click(await screen.findByRole("button", { name: "Analyze selected file" }));
  await screen.findByText("Gemini suitability assessment");
  await userEvent.click(screen.getByRole("button", { name: "Datasets" }));
  expect(screen.getByText("Analysis completed")).toBeVisible();
  expect(screen.getByText(/Analysis completed for resource dataverse-file:11/)).toBeVisible();
});

it("keeps the Pandas profile when Gemini assessment is unavailable", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([zenodoDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(zenodoDataset().dataset_id, [{ id: "zenodo-file:observations.csv", filename: "observations.csv", format: "csv" }]));
    if (url.includes("/datasets/source-analyze")) return jsonResponse(sourceAnalysis(zenodoDataset().dataset_id, "zenodo-file:observations.csv", "observations.csv", { ai: false }));
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  await userEvent.click(await screen.findByRole("button", { name: "Analyze selected file" }));
  expect(await screen.findByText("2 observed records")).toBeVisible();
  expect(screen.getByText("AI assessment unavailable")).toBeVisible();
  expect(screen.getByText("AI suitability assessment unavailable; deterministic profile preserved.")).toBeVisible();
});

it("does not render a statistical report when download or parse fails", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataverseDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(dataverseDataset().dataset_id, [{ id: "dataverse-file:11", filename: "observations.csv", format: "csv" }]));
    if (url.includes("/datasets/source-analyze")) return jsonResponse(sourceAnalysis(dataverseDataset().dataset_id, "dataverse-file:11", "observations.csv", { profile: false, status: "unavailable" }));
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  await userEvent.click(await screen.findByRole("button", { name: "Analyze selected file" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The selected file could not be downloaded or parsed.");
  expect(screen.queryByText("2 observed records")).not.toBeInTheDocument();
  expect(screen.getByText("Rainfall Dataverse")).toBeVisible();
});

it("surfaces an invalid resource identifier from FastAPI", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataverseDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(dataverseDataset().dataset_id, [{ id: "dataverse-file:11", filename: "observations.csv", format: "csv" }]));
    if (url.includes("/datasets/source-analyze")) return jsonResponse({ detail: "The selected resource does not belong to this dataset or is not eligible." }, false, 400);
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  await userEvent.click(await screen.findByRole("button", { name: "Analyze selected file" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("The selected resource does not belong to this dataset or is not eligible.");
});

it("keeps each dataset's resource list isolated during rapid switching", async () => {
  const first = dataverseDataset({ dataset_id: "dataverse:doi:10.5072/FK2/ONE", title: "First Dataverse" });
  const second = zenodoDataset({ dataset_id: "zenodo:999", title: "Second Zenodo" });
  let resolveFirst: ((value: Response) => void) | undefined;
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([first, second]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("dataset_id=dataverse")) {
      return new Promise((resolve) => {
        resolveFirst = resolve;
      }) as Promise<Response>;
    }
    if (url.includes("dataset_id=zenodo")) {
      return jsonResponse(resourceListing(second.dataset_id, [{ id: "zenodo-file:second.csv", filename: "second.csv", format: "csv" }]));
    }
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  const listButtons = screen.getAllByRole("button", { name: "List eligible files" });
  await userEvent.click(listButtons[0]);
  await userEvent.click(listButtons[1]);
  expect(await screen.findByText("second.csv")).toBeVisible();
  resolveFirst?.(jsonResponse(resourceListing(first.dataset_id, [{ id: "dataverse-file:1", filename: "first.csv", format: "csv" }])));
  expect(await screen.findByText("first.csv")).toBeVisible();
  expect(screen.getByText("second.csv")).toBeVisible();
  const firstRow = screen.getByText("First Dataverse").closest("article");
  const secondRow = screen.getByText("Second Zenodo").closest("article");
  expect(firstRow?.textContent).toContain("first.csv");
  expect(firstRow?.textContent).not.toContain("second.csv");
  expect(secondRow?.textContent).toContain("second.csv");
  expect(secondRow?.textContent).not.toContain("first.csv");
});

it("does not let a stale analysis overwrite a newer selection", async () => {
  const dataset = dataverseDataset();
  let resolveSlow: ((value: Response) => void) | undefined;
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataset, uciCropDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(dataset.dataset_id, [{ id: "dataverse-file:11", filename: "observations.csv", format: "csv" }]));
    if (url.includes("/datasets/source-analyze")) {
      return new Promise((resolve) => {
        resolveSlow = resolve;
      }) as Promise<Response>;
    }
    if (url.includes("/analyze")) return jsonResponse(uciAnalysis());
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  await userEvent.click(await screen.findByRole("button", { name: "Analyze selected file" }));
  await userEvent.click(screen.getByRole("button", { name: "Analyze UCI dataset" }));
  expect(await screen.findByText("Live Crop Dataset")).toBeVisible();
  resolveSlow?.(jsonResponse(sourceAnalysis(dataset.dataset_id, "dataverse-file:11", "stale.csv")));
  await waitFor(() => {
    expect(screen.queryByText("stale.csv")).not.toBeInTheDocument();
  });
  expect(screen.getByText("Live Crop Dataset")).toBeVisible();
});

it("keeps dataset details open while files load", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataverseDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse(resourceListing(dataverseDataset().dataset_id, [{ id: "dataverse-file:11", filename: "observations.csv", format: "csv" }]));
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "Details for Rainfall Dataverse" }));
  expect(screen.getByText("rain")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  expect(await screen.findByText("observations.csv")).toBeVisible();
  expect(screen.getByText("rain")).toBeVisible();
  expect(screen.getByRole("button", { name: "Details for Rainfall Dataverse" })).toHaveAttribute("aria-expanded", "true");
});

it("preserves a failed external analysis without destroying the dataset ledger", async () => {
  mockBackend((url) => {
    if (url.includes("/discovery/search")) return jsonResponse(discoveryResponse([dataverseDataset(), uciCropDataset()]));
    if (url.includes("/discovery/graph")) return jsonResponse(graphResponse());
    if (url.includes("/datasets/resources")) return jsonResponse({ detail: "Repository metadata unavailable." }, false, 502);
    return jsonResponse({ detail: "unmocked" }, false, 500);
  });
  await submitQuestion();
  await userEvent.click(await screen.findByRole("button", { name: "Datasets" }));
  await userEvent.click(screen.getByRole("button", { name: "List eligible files" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Repository metadata unavailable.");
  expect(screen.getByText("Rainfall Dataverse")).toBeVisible();
  expect(screen.getByText("Live Crop Dataset")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Graph" }));
  expect(screen.getByRole("heading", { name: "Graph" })).toBeVisible();
});

