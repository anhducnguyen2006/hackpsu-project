export type DatasetStatus = "metadata_only" | "available" | "failed" | "analyzed";

export interface DatasetCardData {
  dataset_id: string;
  title: string;
  source: string;
  description: string | null;
  repository_url: string;
  subject_area: string | null;
  variables: string[];
  instance_count: number | null;
  feature_count: number | null;
  data_available: boolean | null;
  data_status: DatasetStatus;
  preliminary_relevance_score: number | null;
  relevance_explanation: string;
  score_confidence: "low" | "medium" | "high";
}

export interface ResearchInterpretation {
  original_research_question: string;
  research_subject: string;
  independent_variables: string[];
  dependent_variables: string[];
  target_population: string | null;
  synonyms: string[];
  search_terms: string[];
}

export interface DiscoveryResponse {
  interpretation: ResearchInterpretation | null;
  datasets: DatasetCardData[];
  explanation: string;
  warnings: string[];
  processing_mode: "gemini" | "partial_gemini" | "keyword_fallback";
}

export interface NumericSummary {
  count: number;
  mean: number | null;
  median: number | null;
  standard_deviation: number | null;
  minimum: number | null;
  percentile_25: number | null;
  percentile_75: number | null;
  maximum: number | null;
}

export interface ColumnProfile {
  name: string;
  data_type: string;
  measurement_type: string;
  missing_count: number;
  missing_fraction: number;
  unique_count: number;
  is_constant: boolean;
  is_near_empty: boolean;
  research_roles: ("independent" | "outcome" | "related")[];
  numeric_summary: NumericSummary | null;
  categorical_summary: { value: unknown; count: number }[];
}

export interface DataProfile {
  row_count: number;
  column_count: number;
  column_names: string[];
  duplicate_row_count: number;
  columns: ColumnProfile[];
  research_variable_evidence: {
    research_variable: string;
    matched_columns: string[];
    usable_observations: number;
    matched_pairs: Record<string, number>;
    notes: string[];
  }[];
  correlations: {
    column_a: string;
    column_b: string;
    pair_count: number;
    pearson_correlation: number | null;
    limitation: string;
  }[];
  quality_flags: string[];
}

export interface ResearchAssessment {
  dataset_summary: string;
  relevant_independent_variables: string[];
  relevant_outcome_variables: string[];
  missing_or_unverified_research_variables: string[];
  why_useful: string[];
  statistical_methodological_strengths: string[];
  data_quality_issues: string[];
  population_limitations: string[];
  sample_size_considerations: string[];
  recommended_further_analyses: string[];
  overall_assessment: string;
  criteria: Record<string, { score: number | null; explanation: string }>;
  final_score: number | null;
  score_explanation: string;
  ai_status: "available" | "unavailable";
}

export interface DatasetAnalysisResponse {
  dataset: DatasetCardData;
  data_status: "analyzed" | "metadata_only" | "failed";
  profile: DataProfile | null;
  assessment: ResearchAssessment | null;
  ai_assessment_status: "available" | "unavailable";
  warnings: string[];
}

export interface ExploratoryAnalysisResponse {
  dataset_id: string;
  independent_variable: string;
  outcome_variable: string;
  independent_measurement_type: "ordinal_or_encoded_numeric" | "categorical";
  outcome_measurement_type: "numeric";
  categories: {
    category: unknown;
    observations: number;
    mean_outcome: number | null;
    median_outcome: number | null;
    standard_deviation: number | null;
  }[];
  missing_independent_count: number;
  missing_outcome_count: number;
  excluded_observation_count: number;
  analyzed_observation_count: number;
  limitations: string[];
}
