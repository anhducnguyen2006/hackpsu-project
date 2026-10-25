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

it("requires an explicit file choice when several supported resources are present", async () => {
  const onOpenAnalysis = vi.fn();
  const dataset = {
    ...EXAMPLE_DATASETS[0],
    dataset_id: "zenodo:42",
    title: "Rainfall table",
    source: "Zenodo",
    download_resources: [
      { url: "https://zenodo.org/api/records/42/files/a.csv/content", format: "csv", file_id: "a.csv", filename: "a.csv", eligible: true },
      { url: "https://zenodo.org/api/records/42/files/b.csv/content", format: "csv", file_id: "b.csv", filename: "b.csv", eligible: true },
    ],
  };
  render(<DatasetLedger datasets={[dataset]} analysisMode="live" onOpenAnalysis={onOpenAnalysis} />);
  expect(screen.getByText(/Select a data file in the dropdown above to enable Analyze/i)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Analyze dataset" })).not.toBeInTheDocument();
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Data file for Rainfall table" }), "b.csv");
  await userEvent.click(screen.getByRole("button", { name: "Analyze dataset" }));
  expect(onOpenAnalysis).toHaveBeenCalledWith("zenodo:42", "b.csv");
});

it("keeps an unverified filename distinct from a supported file", async () => {
  const onOpenAnalysis = vi.fn();
  const dataset = {
    ...EXAMPLE_DATASETS[0],
    dataset_id: "zenodo:23077368",
    title: "Water storage",
    source: "Zenodo",
    download_resources: [],
    verification_candidates: [
      { url: "https://zenodo.org/api/records/23077368/files/data.csv/content", format: "csv", file_id: "data.csv", filename: "data.csv", eligible: false },
    ],
  };
  render(<DatasetLedger datasets={[dataset]} analysisMode="live" onOpenAnalysis={onOpenAnalysis} />);
  expect(screen.getByText("Not verified. A filename alone is not a download-verified file.")).toBeVisible();
  expect(screen.queryByText(/download verified/i)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Check contents of data.csv" }));
  expect(onOpenAnalysis).toHaveBeenCalledWith("zenodo:23077368", "data.csv");
});

it("does not expand dataset details when the file selector changes", async () => {
  const dataset = {
    ...EXAMPLE_DATASETS[0],
    dataset_id: "zenodo:42",
    title: "Rainfall table",
    source: "Zenodo",
    download_resources: [
      { url: "https://zenodo.org/api/records/42/files/a.csv/content", format: "csv", file_id: "a.csv", filename: "a.csv", eligible: true },
      { url: "https://zenodo.org/api/records/42/files/b.csv/content", format: "csv", file_id: "b.csv", filename: "b.csv", eligible: true },
    ],
  };
  const view = render(<DatasetLedger datasets={[dataset]} analysisMode="live" onOpenAnalysis={() => {}} />);
  const selector = screen.getByRole("combobox", { name: "Data file for Rainfall table" });
  selector.focus();
  expect(selector).toHaveFocus();
  await userEvent.selectOptions(selector, "b.csv");
  expect(screen.queryByText("weekly study time")).not.toBeInTheDocument();
  view.rerender(<DatasetLedger datasets={[{ ...dataset, dataset_id: "zenodo:99", title: "Other table" }]} analysisMode="live" onOpenAnalysis={() => {}} />);
  expect(screen.getByRole("combobox", { name: "Data file for Other table" })).toHaveValue("");
});

it("does not replace null metadata or relevance with zero", () => {
  const sparse = { ...EXAMPLE_DATASETS[1], instance_count: null, feature_count: null, preliminary_relevance_score: null };
  render(<DatasetLedger datasets={[sparse]} onOpenAnalysis={() => {}} />);
  const row = screen.getByRole("article");
  expect(within(row).getByText("Unavailable")).toBeVisible();
  expect(within(row).getAllByText("Not documented").length).toBeGreaterThanOrEqual(2);
  expect(within(row).queryByText("0")).not.toBeInTheDocument();
});

it("shows Dataverse repository metadata beyond DOI in details", async () => {
  const dataset = {
    ...EXAMPLE_DATASETS[0],
    dataset_id: "dataverse:doi:10.7910/DVN/EVNUZS",
    title: "Adolescent Sleep Need Waking EEG, Years 1–3",
    source: "Harvard Dataverse",
    description: "EEG recordings related to adolescent sleep need.",
    authors: ["Example Author"],
    publisher: "Harvard Dataverse",
    publication_date: "2018",
    subjects: ["Medicine, Health and Life Sciences"],
    keywords: ["sleep", "EEG"],
    license: "CC0 1.0",
    doi: "doi:10.7910/DVN/EVNUZS",
    geographic_coverage: [],
    temporal_coverage: ["2011–2013"],
    instance_count: null,
    feature_count: null,
    variables: [],
    variable_descriptions: {},
    matched_research_variables: [],
    score_type: "semantic_similarity" as const,
    semantic_similarity_score: 0.61,
    download_resources: [
      { url: "https://dataverse.harvard.edu/api/access/datafile/1", format: "tab", file_id: "1", filename: "sleep.tab", size_bytes: 2048, eligible: true },
    ],
  };
  render(<DatasetLedger datasets={[dataset]} analysisMode="live" onOpenAnalysis={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "Details for Adolescent Sleep Need Waking EEG, Years 1–3" }));
  expect(screen.getByText("Example Author")).toBeVisible();
  expect(screen.getAllByText("EEG recordings related to adolescent sleep need.").length).toBeGreaterThan(0);
  expect(screen.getByText(/sleep\.tab/)).toBeVisible();
  expect(screen.getAllByText(/Topical similarity/i).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/Unknown until analysis/i).length).toBeGreaterThan(0);
  expect(screen.getByRole("link", { name: "doi:10.7910/DVN/EVNUZS" })).toBeVisible();
});

it("shows Zenodo creators, license, and files in details", async () => {
  const dataset = {
    ...EXAMPLE_DATASETS[0],
    dataset_id: "zenodo:12345",
    title: "Caffeine intake diary",
    source: "Zenodo",
    description: "Self-reported caffeine intake.",
    authors: ["Ada Researcher"],
    publisher: "Zenodo",
    publication_date: "2024-01-15",
    keywords: ["caffeine"],
    license: "cc-by-4.0",
    doi: "10.5281/zenodo.12345",
    variables: [],
    download_resources: [
      { url: "https://zenodo.org/api/records/12345/files/diary.csv/content", format: "csv", file_id: "diary.csv", filename: "diary.csv", size_bytes: 4096, checksum: "md5:abc", eligible: true },
    ],
  };
  render(<DatasetLedger datasets={[dataset]} analysisMode="live" onOpenAnalysis={() => {}} />);
  await userEvent.click(screen.getByRole("button", { name: "Details for Caffeine intake diary" }));
  expect(screen.getByText("Ada Researcher")).toBeVisible();
  expect(screen.getByText("cc-by-4.0")).toBeVisible();
  expect(screen.getByText(/diary\.csv/)).toBeVisible();
  expect(screen.getByText(/checksum md5:abc/)).toBeVisible();
});
