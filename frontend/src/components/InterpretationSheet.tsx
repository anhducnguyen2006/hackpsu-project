import type { DiscoveryResponse, ResearchInterpretation } from "../types";
import { normalizeResearchInterpretation } from "../api/interpretation";
import { EvidenceTag } from "./EvidenceTag";
import { useState } from "react";

function displayValue(value: string, unavailable: boolean): string {
  if (unavailable) return "Unavailable";
  return value || "Not specified";
}

export function InterpretationSheet({ interpretation, processingMode, onSearchQuestion }: { interpretation: ResearchInterpretation | null; processingMode?: DiscoveryResponse["processing_mode"]; onSearchQuestion?: (question: string) => Promise<void> | void }) {
  const prepared = normalizeResearchInterpretation(interpretation);
  const view = prepared.interpretation;
  const unavailable = new Set(prepared.unavailableFields);
  const [refinedQuestion, setRefinedQuestion] = useState(view?.refined_question ?? "");
  const [showRefinement, setShowRefinement] = useState(Boolean(view?.refined_question));
  const [refinementStatus, setRefinementStatus] = useState("");
  const contractWarning = prepared.warnings.length > 0
    ? <div className="warning-state" role="status"><p>This interpretation response did not match the expected contract. Only fields that arrived intact are shown.</p><ul>{prepared.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>
    : null;
  if (!view) {
    return <section className="workspace-grid interpretation-page" aria-labelledby="interpretation-title"><div className="workspace-content"><p className="eyebrow">Research instrument / 02 — Interpretation</p><h1 id="interpretation-title">Interpretation</h1>{contractWarning}<div className="empty-state" role="status"><h2>Interpretation unavailable</h2><p>The discovery service did not return an interpretation for this question. Revise the question and try again.</p></div></div><aside className="context-rail"><p className="eyebrow">Search method</p><h2>Terms &amp; scope</h2><p className="rail-note">No interpreted concepts are available yet.</p></aside></section>;
  }
  async function useRefinement() {
    if (!onSearchQuestion || refinedQuestion.trim().length < 10) return;
    setRefinementStatus("Searching with the edited question…");
    try {
      await onSearchQuestion(refinedQuestion.trim());
    } catch (error) {
      setRefinementStatus(error instanceof Error ? error.message : "The revised search failed.");
    }
  }
  const fields = [
    ["Subject", displayValue(view.research_subject, unavailable.has("research_subject"))],
    ["Independent variable", displayValue(view.independent_variables.join(", "), unavailable.has("independent_variables"))],
    ["Outcome", displayValue(view.dependent_variables.join(", "), unavailable.has("dependent_variables"))],
    ["Population", unavailable.has("target_population") ? "Unavailable" : view.target_population ?? "Not specified"],
  ];
  const synonyms = displayValue(view.synonyms.join(", "), unavailable.has("synonyms"));
  const assumptions = view.assumptions_or_ambiguities;
  return <section className="workspace-grid interpretation-page" aria-labelledby="interpretation-title">
    <div className="workspace-content"><p className="eyebrow">Research instrument / 02 — Interpretation</p><h1 id="interpretation-title">Interpretation</h1>
      <p className="section-deck">This question has been parsed into concepts for dataset discovery. These terms are interpretations, not verified dataset columns.</p>
      {contractWarning}
      <EvidenceTag label={processingMode === "keyword_fallback" ? "Keyword fallback interpretation" : processingMode ? "AI interpretation" : "Interpretation unavailable"} explanation="Concepts inferred from the question for search; dataset columns are verified separately." />
      {showRefinement && refinedQuestion && processingMode !== "keyword_fallback" && <div className="refinement-card" aria-label="Refined question suggestion"><span className="data-label">Suggested search wording</span><p>Gemini made the question more searchable without changing its intended meaning. Edit, use, or reject this suggestion.</p><textarea value={refinedQuestion} onChange={(event) => setRefinedQuestion(event.target.value)} rows={3} /><div className="refinement-actions"><button type="button" className="primary-action" onClick={useRefinement} disabled={!onSearchQuestion}>Use edited question</button><button type="button" className="secondary-action" onClick={() => { setShowRefinement(false); setRefinementStatus(""); }}>Reject suggestion</button></div>{refinementStatus && <p role="status" className="form-status">{refinementStatus}</p>}</div>}
      <div className="interpretation-sheet">{fields.map(([name, value], index) => <div className="interpretation-cell" key={name}><span className="data-label">0{index + 1} / {name}</span><strong>{value}</strong></div>)}</div>
      <div className="interpretation-source"><span className="data-label">Original question</span><blockquote>{unavailable.has("original_research_question") ? "Unavailable" : view.original_research_question}</blockquote></div>
    </div>
      <aside className="context-rail"><p className="eyebrow">Search method</p><h2>Terms &amp; scope</h2><div className="rail-block"><span className="data-label">Synonym</span><p>{synonyms}</p></div><div className="rail-block"><span className="data-label">Geographic scope</span><p>{unavailable.has("geographic_scope") ? "Unavailable" : view.geographic_scope ?? "Not specified"}</p></div><div className="rail-block"><span className="data-label">Temporal scope</span><p>{unavailable.has("temporal_scope") ? "Unavailable" : view.temporal_scope ?? "Not specified"}</p></div><div className="rail-block"><span className="data-label">Search terms</span>{unavailable.has("search_terms") ? <p>Unavailable</p> : view.search_terms.length === 0 ? <p>Not specified</p> : <ol>{view.search_terms.map((term) => <li key={term}>{term}</li>)}</ol>}</div>{unavailable.has("assumptions_or_ambiguities") ? <div className="rail-block"><span className="data-label">Ambiguities</span><p>Unavailable</p></div> : assumptions.length > 0 && <div className="rail-block"><span className="data-label">Ambiguities</span><p>{assumptions.join(" ")}</p></div>}<p className="rail-note">These terms guide repository discovery. Verify variables against each source record before analysis.</p></aside>
  </section>;
}
