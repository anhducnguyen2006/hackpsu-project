import type { DiscoveryResponse, ResearchInterpretation } from "../types";
import { EvidenceTag } from "./EvidenceTag";

export function InterpretationSheet({ interpretation, processingMode }: { interpretation: ResearchInterpretation | null; processingMode?: DiscoveryResponse["processing_mode"] }) {
  if (!interpretation) {
    return <section className="workspace-grid interpretation-page" aria-labelledby="interpretation-title"><div className="workspace-content"><p className="eyebrow">Research instrument / 02 — Interpretation</p><h1 id="interpretation-title">Interpretation</h1><div className="empty-state" role="status"><h2>Interpretation unavailable</h2><p>The discovery service did not return an interpretation for this question. Revise the question and try again.</p></div></div><aside className="context-rail"><p className="eyebrow">Search method</p><h2>Terms &amp; scope</h2><p className="rail-note">No interpreted concepts are available yet.</p></aside></section>;
  }
  const fields = [
    ["Subject", interpretation.research_subject], ["Independent variable", interpretation.independent_variables.join(", ")],
    ["Outcome", interpretation.dependent_variables.join(", ")], ["Population", interpretation.target_population ?? "Not specified"],
  ];
  return <section className="workspace-grid interpretation-page" aria-labelledby="interpretation-title">
    <div className="workspace-content"><p className="eyebrow">Research instrument / 02 — Interpretation</p><h1 id="interpretation-title">Interpretation</h1>
      <p className="section-deck">This question has been parsed into concepts for dataset discovery. These terms are interpretations, not verified dataset columns.</p>
      <EvidenceTag label={processingMode === "keyword_fallback" ? "Keyword fallback interpretation" : processingMode ? "AI interpretation" : "Interpretation unavailable"} explanation="Concepts inferred from the question for search; dataset columns are verified separately." />
      <div className="interpretation-sheet">{fields.map(([name, value], index) => <div className="interpretation-cell" key={name}><span className="data-label">0{index + 1} / {name}</span><strong>{value}</strong></div>)}</div>
      <div className="interpretation-source"><span className="data-label">Original question</span><blockquote>{interpretation.original_research_question}</blockquote></div>
    </div>
      <aside className="context-rail"><p className="eyebrow">Search method</p><h2>Terms &amp; scope</h2><div className="rail-block"><span className="data-label">Synonym</span><p>{interpretation.synonyms.join(", ") || "Not specified"}</p></div><div className="rail-block"><span className="data-label">Search terms</span><ol>{interpretation.search_terms.map((term) => <li key={term}>{term}</li>)}</ol></div><p className="rail-note">These terms guide repository discovery. Verify variables against each source record before analysis.</p></aside>
  </section>;
}
