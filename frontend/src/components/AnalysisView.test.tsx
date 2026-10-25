import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EXAMPLE_ANALYSIS, EXAMPLE_EXPLORATION } from "../demo/researchExample";
import type { DatasetAnalysisResponse } from "../types";
import { AnalysisView } from "./AnalysisView";

const liveAnalysis: DatasetAnalysisResponse = {
  dataset: {
    ...EXAMPLE_ANALYSIS.dataset,
    dataset_id: "zenodo:23077368",
    title: "Monthly water storage",
    source: "Zenodo",
    repository_url: "https://zenodo.org/records/23077368",
  },
  data_status: "analyzed",
  profile: {
    ...EXAMPLE_ANALYSIS.profile!,
    row_count: 12474,
    column_count: 3,
    duplicate_row_count: 0,
    columns: [
      {
        name: "storage_ml",
        data_type: "float64",
        measurement_type: "numeric",
        missing_count: 0,
        missing_fraction: 0,
        unique_count: 100,
        is_constant: false,
        is_near_empty: false,
        numeric_summary: { count: 12474, mean: 15, median: 14, standard_deviation: 1, minimum: 1, percentile_25: 2, percentile_75: 3, maximum: 4 },
        categorical_summary: [],
        research_roles: [],
      },
    ],
    research_variable_evidence: [],
    correlations: [],
    quality_flags: ["Row count is not necessarily the number of independent participants."],
  },
  assessment: {
    dataset_summary: "Verified file.",
    relevant_independent_variables: ["month_end"],
    relevant_outcome_variables: ["storage_ml"],
    missing_or_unverified_research_variables: [],
    why_useful: ["The file contains the requested columns."],
    statistical_methodological_strengths: ["The profile is computed from the file."],
    data_quality_issues: [],
    population_limitations: [],
    sample_size_considerations: ["Rows are observations."],
    recommended_further_analyses: ["Inspect the time index."],
    overall_assessment: "Potentially useful.",
    criteria: {
      research_question_and_outcome_alignment: { score: 80, explanation: "The outcome column is present." },
      required_variable_coverage: { score: 80, explanation: "Columns were parsed." },
      sample_size_considerations: { score: 80, explanation: "Many rows were parsed." },
      data_quality_and_completeness: { score: 80, explanation: "Missingness was measured." },
      documentation_and_provenance: { score: 80, explanation: "The DOI is present." },
      population_and_temporal_relevance: { score: 80, explanation: "The version is recorded." },
    },
    final_score: 80,
    score_explanation: "Python recomputed this score from the six criterion scores.",
    ai_status: "available",
  },
  ai_assessment_status: "available",
  warnings: ["Provider type metadata was inconclusive. The file was parsed before it was marked download-verified."],
  analyzed_resource: {
    url: "https://zenodo.org/api/records/23077368/files/data.csv/content",
    format: "csv",
    file_id: "data.csv",
    filename: "data.csv",
    checksum: "md5:abc",
    eligible: true,
  },
  eligibility_status: "download_verified",
  download_performed: true,
  research_query_id: 44,
  history_saved: true,
  source_doi: "10.5281/zenodo.23077368",
  source_version: "2025-10-31",
};

it("shows cached computed values without a fabricated suitability score", () => {
  render(<AnalysisView analysis={EXAMPLE_ANALYSIS} />);
  for (const value of ["649 observed records", "33 columns", "0 duplicate rows", "Computed profile", "studytime", "G3", "1: 212", "2: 305", "3: 97", "4: 35", "11.91", "12"]) {
    expect(screen.getAllByText(value).length).toBeGreaterThan(0);
  }
  expect(screen.getByText(/two cached variable profiles of 33 total columns/i)).toBeVisible();
  expect(screen.getByText("ordinal")).toBeVisible();
  expect(screen.getByText("weekly study time")).toBeVisible();
  expect(screen.getAllByText("Unavailable")).toHaveLength(7);
  expect(screen.getByText(/do not establish causation/i)).toBeVisible();
  expect(screen.queryByText(/suitability.*\/100/i)).not.toBeInTheDocument();
});

it("shows live file statistics and the Python suitability score without the demo chart", () => {
  render(<AnalysisView analysis={liveAnalysis} exploration={EXAMPLE_EXPLORATION} presentation="computed" />);
  expect(screen.getByText("Parsed file: data.csv")).toBeVisible();
  expect(screen.getByText("12474 observed records")).toBeVisible();
  expect(screen.getByText("storage_ml")).toBeVisible();
  expect(screen.getByText("15.00")).toBeVisible();
  expect(screen.getAllByText("80").length).toBeGreaterThan(0);
  expect(screen.getByText("Python suitability score")).toBeVisible();
  expect(screen.getByText("DOI: 10.5281/zenodo.23077368")).toBeVisible();
  expect(screen.getByText("Source version: 2025-10-31")).toBeVisible();
  expect(screen.getByText("Checksum: md5:abc")).toBeVisible();
  expect(screen.getByText(/parsed before it was marked download-verified/i)).toBeVisible();
  expect(screen.queryByText("Cached demo")).not.toBeInTheDocument();
  expect(screen.queryByText("Study time & final grade")).not.toBeInTheDocument();
  expect(screen.queryByText(/Rows in cached profile/)).not.toBeInTheDocument();
});

it("shows an explicit unavailable assessment without inventing a score", () => {
  render(<AnalysisView analysis={{ ...liveAnalysis, assessment: null, ai_assessment_status: "unavailable", history_saved: false, warnings: ["AI suitability assessment unavailable: model unavailable"] }} presentation="computed" />);
  expect(screen.getByText("Live AI assessment unavailable")).toBeVisible();
  expect(screen.getAllByText(/AI suitability assessment unavailable/i).length).toBeGreaterThan(0);
  expect(screen.queryByText(/No verifiable cached AI assessment/i)).not.toBeInTheDocument();
  expect(screen.getByText("This result was not saved to Past Research.")).toBeVisible();
  expect(screen.getByText("12474 observed records")).toBeVisible();
  expect(screen.queryByText("Python suitability score")).not.toBeInTheDocument();
});

it("keeps cached-demo wording only for the preview example", () => {
  render(<AnalysisView analysis={EXAMPLE_ANALYSIS} presentation="preview" />);
  expect(screen.getAllByText(/No verifiable cached AI assessment/i).length).toBeGreaterThan(0);
  expect(screen.queryByText("Live AI assessment unavailable")).not.toBeInTheDocument();
});
