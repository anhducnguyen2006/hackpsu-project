import { expect, it } from "vitest";
import { EXAMPLE_INTERPRETATION } from "../demo/researchExample";
import { normalizeResearchInterpretation } from "./interpretation";

it("preserves a populated interpretation exactly", () => {
  const prepared = normalizeResearchInterpretation(EXAMPLE_INTERPRETATION);
  expect(prepared.warnings).toEqual([]);
  expect(prepared.unavailableFields).toEqual([]);
  expect(prepared.interpretation).toEqual(EXAMPLE_INTERPRETATION);
});

it("treats omitted and null optional ambiguities as an empty list", () => {
  const { assumptions_or_ambiguities: _omitted, ...withoutAmbiguities } = EXAMPLE_INTERPRETATION;
  const omitted = normalizeResearchInterpretation(withoutAmbiguities);
  const nulled = normalizeResearchInterpretation({ ...EXAMPLE_INTERPRETATION, assumptions_or_ambiguities: null });
  expect(omitted.warnings).toEqual([]);
  expect(omitted.interpretation?.assumptions_or_ambiguities).toEqual([]);
  expect(nulled.warnings).toEqual([]);
  expect(nulled.interpretation?.assumptions_or_ambiguities).toEqual([]);
});

it("keeps a legitimate empty required array distinct from a missing one", () => {
  const empty = normalizeResearchInterpretation({ ...EXAMPLE_INTERPRETATION, synonyms: [] });
  const missing = normalizeResearchInterpretation({ ...EXAMPLE_INTERPRETATION, synonyms: undefined });
  expect(empty.warnings).toEqual([]);
  expect(empty.unavailableFields).not.toContain("synonyms");
  expect(empty.interpretation?.synonyms).toEqual([]);
  expect(missing.unavailableFields).toContain("synonyms");
  expect(missing.warnings).toContain("Synonyms were missing from the discovery response.");
  expect(missing.interpretation?.synonyms).toEqual([]);
  expect(missing.interpretation?.independent_variables).toEqual(EXAMPLE_INTERPRETATION.independent_variables);
});

it("does not invent values when a required list or ambiguity list is malformed", () => {
  const prepared = normalizeResearchInterpretation({
    ...EXAMPLE_INTERPRETATION,
    assumptions_or_ambiguities: "pollution might mean air pollution",
    search_terms: "rainfall, crop, yield",
    independent_variables: ["rainfall", 3],
  });
  expect(prepared.interpretation?.assumptions_or_ambiguities).toEqual([]);
  expect(prepared.interpretation?.search_terms).toEqual([]);
  expect(prepared.interpretation?.independent_variables).toEqual(["rainfall"]);
  expect(prepared.unavailableFields).toEqual(expect.arrayContaining(["assumptions_or_ambiguities", "search_terms"]));
  expect(prepared.warnings.join(" ")).not.toMatch(/air pollution|crop yield/);
});

it("reports a non-object interpretation without fabricating concepts", () => {
  const prepared = normalizeResearchInterpretation("not an interpretation");
  expect(prepared.interpretation).toBeNull();
  expect(prepared.warnings).toEqual(["The discovery response did not include an interpretation object."]);
});
