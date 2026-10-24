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
