export type DatasetStatus = "metadata_only" | "available" | "failed" | "analyzed";

export interface DatasetCardData {
  dataset_id: string;
  title: string;
  source: string;
  description?: string;
  repository_url: string;
  data_status: DatasetStatus;
  provisional_score?: {
    value: number;
    confidence: "low" | "medium" | "high";
  };
}

