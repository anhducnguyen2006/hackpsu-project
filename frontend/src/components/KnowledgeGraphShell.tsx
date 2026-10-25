import type { DatasetAnalysisResponse, DatasetCardData, ResearchInterpretation } from "../types";
import { EvidenceTag } from "./EvidenceTag";

type Relation = { id: string; from: string; to: string; label: string; source: string; x1: number; y1: number; x2: number; y2: number };
type Node = { key: string; title: string; type: string; x: number; y: number; verified?: boolean };

export function KnowledgeGraphShell({ interpretation, datasets, analysis }: { interpretation: ResearchInterpretation | null; datasets: DatasetCardData[]; analysis: DatasetAnalysisResponse | null }) {
  const concepts = interpretation ? [
    ...interpretation.independent_variables.map((text) => ({ text, type: "independent variable" })),
    ...interpretation.dependent_variables.map((text) => ({ text, type: "outcome variable" })),
  ].filter((concept) => concept.text.trim()) : [];
  const visibleConcepts = concepts.slice(0, 4);
  const visibleDatasets = datasets.slice(0, 2);
  const evidence = analysis?.profile?.research_variable_evidence ?? [];
  const nodes: Node[] = [
    { key: "question", title: "Question", type: "research question", x: 90, y: 200 },
    ...visibleConcepts.map((concept, index) => ({ key: `concept-${index}`, title: concept.text, type: "interpreted concept", x: 320, y: 90 + index * 105 })),
    ...visibleDatasets.map((dataset, index) => ({ key: `dataset-${index}`, title: dataset.dataset_id, type: dataset.source, x: 600, y: 130 + index * 140 })),
    ...evidence.slice(0, 4).flatMap((item, index) => item.matched_columns.slice(0, 1).map((column) => ({ key: `variable-${index}`, title: column, type: "verified column", x: 840, y: 70 + index * 80, verified: true }))),
  ];
  const positions = Object.fromEntries(nodes.map((node) => [node.key, [node.x, node.y] as [number, number]]));
  const relation = (id: string, from: string, to: string, label: string, source: string): Relation | null => {
    const start = positions[from];
    const end = positions[to];
    if (!start || !end) return null;
    return { id, from, to, label, source, x1: start[0], y1: start[1], x2: end[0], y2: end[1] };
  };
  const relations: Relation[] = [];
  visibleConcepts.forEach((concept, index) => {
    const edge = relation(`question-concept-${index}`, "question", `concept-${index}`, "interpreted concept", interpretation?.search_terms.length ? "Concept extracted from the submitted research question." : "No search terms were returned.");
    if (edge) relations.push({ ...edge, from: "Question", to: concept.text });
  });
  visibleDatasets.forEach((dataset, datasetIndex) => {
    const matches = dataset.concept_matches ?? [];
    matches.slice(0, 3).forEach((match, matchIndex) => {
      const conceptIndex = visibleConcepts.findIndex((concept) => concept.text === match.concept);
      const edge = conceptIndex >= 0 ? relation(`concept-dataset-${datasetIndex}-${matchIndex}`, `concept-${conceptIndex}`, `dataset-${datasetIndex}`, "metadata match", match.evidence.join(" ") || dataset.relevance_explanation) : null;
      if (edge) relations.push({ ...edge, from: visibleConcepts[conceptIndex].text, to: dataset.dataset_id });
    });
  });
  evidence.slice(0, 4).forEach((item, evidenceIndex) => {
    const conceptIndex = visibleConcepts.findIndex((concept) => concept.text.toLowerCase() === item.research_variable.toLowerCase());
    const column = item.matched_columns[0];
    const edge = conceptIndex >= 0 && column ? relation(`concept-variable-${evidenceIndex}`, `concept-${conceptIndex}`, `variable-${evidenceIndex}`, "verified variable mapping", item.notes.join(" ") || "Verified by the computed profile.") : null;
    if (edge) relations.push({ ...edge, from: visibleConcepts[conceptIndex].text, to: column });
  });
  const firstEvidence = evidence[0];
  const live = Boolean(interpretation && datasets.length);
  return <section className="graph-page" aria-labelledby="graph-title"><div className="graph-heading"><div><p className="eyebrow">Research instrument / 04 — Graph</p><h1 id="graph-title">Graph</h1><p className="section-deck">{live ? "An evidence map of the submitted question and returned repository metadata. The relation list is the complete readable version." : "An evidence map is available after a live interpretation and dataset discovery response."}</p></div><EvidenceTag label={live ? "Live discovery" : "Cached demo"} explanation={live ? "Only interpreted concepts and repository evidence returned by the discovery response are shown." : "Only cached UCI metadata and computed variable evidence are shown."} /></div>
    <div className="graph-grid"><div className="graph-main"><div className="graph-canvas"><div className="graph-canvas-header"><span className="data-label">Fig. 02 / Evidence topology</span><span>Fixed diagram · no interaction</span></div><svg viewBox="0 0 960 400" role="img" aria-label="Evidence topology; all relations are listed below" preserveAspectRatio="xMidYMid meet">
      <g className="graph-guides" aria-hidden="true"><path d="M 0 200 H 960 M 320 0 V 400 M 600 0 V 400" /></g>
      {relations.map((edge) => <line key={edge.id} data-edge-id={edge.id} x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} className={edge.label === "verified variable mapping" ? "verified-edge" : "metadata-edge"} />)}
      {nodes.map((node) => <g key={node.key} transform={`translate(${node.x},${node.y})`}><circle r="9" className={node.verified ? "verified-node" : "ordinary-node"} /><text x="0" y="-22" textAnchor="middle">{node.title}</text><text x="0" y="32" textAnchor="middle" className="node-type">{node.type}</text></g>)}
    </svg><div className="graph-legend"><span><i className="legend-dot" /> Evidence node</span><span><i className="legend-line" /> Documented relation</span><span><i className="legend-line verified" /> Verified column mapping</span></div></div>
    <section className="relation-section" aria-labelledby="relation-title"><div className="relation-heading"><span className="data-label">Evidence list / complete equivalent</span><h2 id="relation-title">Relations</h2></div>{relations.length ? <ol className="relation-list">{relations.map((edge) => <li key={edge.id} data-relation-id={edge.id}><div><strong>{edge.from} → {edge.to}</strong><span className="data-label">{edge.label}</span></div><p>{edge.source}</p></li>)}</ol> : <p className="empty-state" role="status">No evidence-backed relations are available yet.</p>}</section></div>
    <aside className="graph-inspector"><span className="data-label">Inspector / evidence status</span><h2>{firstEvidence ? "Selected variable mapping" : "No verified mapping"}</h2><p>{firstEvidence ? `Research variable: ${firstEvidence.research_variable}. Verified column: ${firstEvidence.matched_columns.join(", ")}. ${firstEvidence.notes.join(" ")}` : "Verified variable mappings appear after a dataset has been analyzed."}</p><EvidenceTag label={firstEvidence ? "Computed profile" : "Metadata only"} explanation={firstEvidence ? "Research variable mapping is documented in the computed analysis profile." : "Discovery metadata does not establish a verified data-column mapping."} /><div className="publication-empty"><span className="data-label">Publication layer</span><p>No verified publication links are available.</p></div></aside></div>
  </section>;
}
