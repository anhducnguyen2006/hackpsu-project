import { describe, expect, it } from "vitest";
import { EXAMPLE_QUESTION, EXAMPLE_DATASETS, EXAMPLE_ANALYSIS, EXAMPLE_EXPLORATION } from "./researchExample";

describe("cached UCI example", () => {
  it("uses only documented records and an honest assessment state", () => {
    expect(EXAMPLE_QUESTION).toBe("How is study time associated with academic performance?");
    expect(EXAMPLE_DATASETS.map((dataset) => dataset.dataset_id)).toEqual(["uci:320", "uci:856"]);
    expect(EXAMPLE_DATASETS.map((dataset) => dataset.instance_count)).toEqual([649, 145]);
    expect(EXAMPLE_DATASETS.map((dataset) => dataset.preliminary_relevance_score)).toEqual([92, 48]);
    expect(EXAMPLE_ANALYSIS.profile?.row_count).toBe(649);
    expect(EXAMPLE_ANALYSIS.assessment?.final_score).toBeNull();
    expect(EXAMPLE_EXPLORATION.analyzed_observation_count).toBe(649);
    expect(EXAMPLE_DATASETS.every((dataset) => !("publication" in dataset))).toBe(true);
  });
});
