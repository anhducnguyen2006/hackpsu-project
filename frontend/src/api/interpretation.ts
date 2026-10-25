import type { ResearchInterpretation } from "../types";

/**
 * Runtime boundary for discovery interpretation payloads.
 *
 * Valid values pass through unchanged. Optional ambiguities may be omitted.
 * Required research fields stay required: a malformed field is marked
 * unavailable and is never replaced with invented scientific content.
 */
export interface PreparedInterpretation {
  interpretation: ResearchInterpretation | null;
  warnings: string[];
  unavailableFields: string[];
}

const REQUIRED_TEXT_FIELDS = [
  ["original_research_question", "Original question"],
  ["research_subject", "Research subject"],
] as const;

const OPTIONAL_TEXT_FIELDS = [
  ["refined_question", "Refined question"],
  ["target_population", "Population"],
  ["population", "Population description"],
  ["geographic_scope", "Geographic scope"],
  ["temporal_scope", "Temporal scope"],
] as const;

const REQUIRED_ARRAY_FIELDS = [
  ["independent_variables", "Independent variables"],
  ["dependent_variables", "Outcome variables"],
  ["synonyms", "Synonyms"],
  ["search_terms", "Search terms"],
] as const;

const OPTIONAL_ARRAY_FIELDS = [
  ["assumptions_or_ambiguities", "Assumptions or ambiguities"],
] as const;

export function normalizeResearchInterpretation(value: unknown): PreparedInterpretation {
  if (value == null) {
    return { interpretation: null, warnings: [], unavailableFields: [] };
  }
  if (typeof value !== "object" || Array.isArray(value)) {
    return {
      interpretation: null,
      warnings: ["The discovery response did not include an interpretation object."],
      unavailableFields: [],
    };
  }

  const record = value as Record<string, unknown>;
  const warnings: string[] = [];
  const unavailableFields: string[] = [];
  const interpretation: ResearchInterpretation = {
    original_research_question: "",
    refined_question: null,
    research_subject: "",
    independent_variables: [],
    dependent_variables: [],
    target_population: null,
    population: null,
    geographic_scope: null,
    temporal_scope: null,
    synonyms: [],
    assumptions_or_ambiguities: [],
    search_terms: [],
  };

  for (const [field, label] of REQUIRED_TEXT_FIELDS) {
    const raw = record[field];
    if (typeof raw === "string") {
      interpretation[field] = raw;
      continue;
    }
    unavailableFields.push(field);
    warnings.push(
      raw == null
        ? `${label} was missing from the discovery response.`
        : `${label} was not text in the discovery response.`,
    );
  }

  for (const [field, label] of OPTIONAL_TEXT_FIELDS) {
    if (!(field in record) || record[field] == null) {
      interpretation[field] = null;
      continue;
    }
    if (typeof record[field] === "string") {
      interpretation[field] = record[field];
      continue;
    }
    interpretation[field] = null;
    unavailableFields.push(field);
    warnings.push(`${label} was not text in the discovery response.`);
  }

  for (const [field, label] of REQUIRED_ARRAY_FIELDS) {
    interpretation[field] = readStringArray(record, field, label, true, warnings, unavailableFields);
  }
  for (const [field, label] of OPTIONAL_ARRAY_FIELDS) {
    interpretation[field] = readStringArray(record, field, label, false, warnings, unavailableFields);
  }

  return { interpretation, warnings, unavailableFields };
}

function readStringArray(
  record: Record<string, unknown>,
  field: keyof ResearchInterpretation,
  label: string,
  required: boolean,
  warnings: string[],
  unavailableFields: string[],
): string[] {
  if (!(field in record) || record[field] == null) {
    if (required) {
      unavailableFields.push(field);
      warnings.push(`${label} were missing from the discovery response.`);
    }
    return [];
  }
  const raw = record[field];
  if (!Array.isArray(raw)) {
    unavailableFields.push(field);
    warnings.push(`${label} were not a list in the discovery response.`);
    return [];
  }
  const values = raw.filter((item): item is string => typeof item === "string");
  if (values.length !== raw.length) {
    warnings.push(`${label} included values that were not text. Those values were omitted.`);
    if (values.length === 0) {
      unavailableFields.push(field);
    }
  }
  return values;
}
