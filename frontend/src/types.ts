export type DatasetStatus = "metadata_only" | "available" | "failed" | "analyzed";

export type EligibilityStatus =
  | "supported_resource_verified"
  | "download_verified"
  | "unsupported"
  | "restricted"
  | "verification_failed"
  | "unverified";

export interface DownloadResource {
  url: string;
  format: string;
  file_id?: string | null;
  filename?: string | null;
  original_filename?: string | null;
  content_type?: string | null;
  original_format?: string | null;
  size_bytes?: number | null;
  checksum?: string | null;
  access_status?: string | null;
  eligible?: boolean;
}

export interface ConceptMatch {
  concept_id: string;
  concept_type: "full_question" | "independent_variable" | "dependent_variable" | "population_or_geography" | "research_subject" | "synonym" | "search_term";
  concept: string;
  matched_terms: string[];
  matched_fields: string[];
  evidence: string[];
  semantic_similarity_score: number | null;
}

export interface DatasetCardData {
  dataset_id: string;
  title: string;
  source: string;
  description: string | null;
  repository_url: string;
  subject_area: string | null;
  variables: string[];
  variable_descriptions?: Record<string, string>;
  instance_count: number | null;
  feature_count: number | null;
  data_available: boolean | null;
  source_id?: string | null;
  landing_page_url?: string | null;
  download_resources?: DownloadResource[];
  subjects?: string[];
  geographic_coverage?: string[];
  temporal_coverage?: string[];
  doi?: string | null;
  license?: string | null;
  eligibility_status?: EligibilityStatus;
  eligibility_reason?: string | null;
  download_performed?: boolean;
  source_version?: string | null;
  data_status: DatasetStatus;
  preliminary_relevance_score: number | null;
  semantic_similarity_score?: number | null;
  score_type?: "semantic_similarity" | "keyword_fallback" | "legacy_gemini";
  concept_matches?: ConceptMatch[];
  relevance_explanation: string;
  score_confidence: "low" | "medium" | "high";
  matched_research_variables?: string[];
  missing_or_unverified_variables?: string[];
  classification?: "relevant" | "partially_relevant" | "irrelevant";
  verification_candidates?: DownloadResource[];
}

export interface ResearchInterpretation {
  original_research_question: string;
  refined_question: string | null;
  research_subject: string;
  independent_variables: string[];
  dependent_variables: string[];
  target_population: string | null;
  population: string | null;
  geographic_scope: string | null;
  temporal_scope: string | null;
  synonyms: string[];
  assumptions_or_ambiguities: string[];
  search_terms: string[];
}

export interface DiscoveryResponse {
  interpretation: ResearchInterpretation | null;
  datasets: DatasetCardData[];
  explanation: string;
  warnings: string[];
  processing_mode: "gemini" | "partial_gemini" | "keyword_fallback";
  ranking_status?: "semantic_embeddings" | "keyword_fallback" | "unavailable" | "demo_cached";
  research_query_id?: number | null;
}

export interface ResearchHistoryItem {
  id: number;
  question: string;
  normalized_question: string;
  created_at: string;
}

export interface SimilarResearchItem extends ResearchHistoryItem {
  similarity_score: number;
}

export interface SimilarResearchRequest {
  research_question: string;
}

export interface SavedDatasetMatch {
  metadata: Record<string, unknown>;
  rank: number | null;
  relevance_score: number | null;
  explanation: string | null;
}

export interface SavedAssessment {
  dataset_id: number | string;
  model?: string;
  assessment_version?: string;
  assessment: Record<string, unknown>;
  suitability_score?: number | null;
  created_at?: string;
}

export interface ResearchSession extends ResearchHistoryItem {
  datasets: SavedDatasetMatch[];
  assessments: SavedAssessment[];
}

export type GraphNodeType = "DATASET" | "VARIABLE" | "GEOGRAPHY" | "TIME_PERIOD" | "RESEARCH_CONCEPT";

export interface DatasetGraphNodeData {
  id: string;
  type: GraphNodeType | string;
  label: string;
  source?: string;
  concept_type?: string;
}

export interface DatasetGraphEdgeData {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  evidence: string;
  verification_status: string;
}

export interface DatasetGraphResponse {
  nodes: { data: DatasetGraphNodeData }[];
  edges: { data: DatasetGraphEdgeData }[];
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
  analyzed_resource?: DownloadResource | null;
  eligibility_status?: EligibilityStatus | null;
  download_performed?: boolean;
  research_query_id?: number | null;
  history_saved?: boolean;
  source_doi?: string | null;
  source_version?: string | null;
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
