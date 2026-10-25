import type { DatasetAnalysisResponse, DatasetCardData, ResearchInterpretation } from "../types";
import { EvidenceTag } from "./EvidenceTag";

type Relation = { id: string; from: string; to: string; label: string; source: string; x1: number; y1: number; x2: number; y2: number };

export function KnowledgeGraphShell({ interpretation, datasets, analysis }: { interpretation: ResearchInterpretation; datasets: DatasetCardData[]; analysis: DatasetAnalysisResponse }) {
  const independent = interpretation.independent_variables[0];
  const outcome = interpretation.dependent_variables[0];
  const coordinates = { question: [90, 200], independent: [320, 90], outcome: [320, 310], first: [600, 130], second: [600, 270], variable: [840, 90], grade: [840, 310] };
  const relation = (id: string, from: string, to: string, label: string, source: string, start: keyof typeof coordinates, end: keyof typeof coordinates): Relation => {
    const [x1, y1] = coordinates[start]; const [x2, y2] = coordinates[end];
    return { id, from, to, label, source, x1, y1, x2, y2 };
  };
  const firstDataset = datasets[0];
  const secondDataset = datasets[1];
  const evidence = analysis.profile?.research_variable_evidence ?? [];
  const relations: Relation[] = [
    relation("question-study", "Question", independent, "interpreted concept", "Keyword fallback interpretation of the example question.", "question", "independent"),
    relation("question-outcome", "Question", outcome, "interpreted concept", "Keyword fallback interpretation of the example question.", "question", "outcome"),
    ...(firstDataset ? [relation("study-uci320", independent, firstDataset.dataset_id, "metadata match", firstDataset.relevance_explanation, "independent", "first")] : []),
    ...(secondDataset ? [relation("study-uci856", independent, secondDataset.dataset_id, "metadata candidate", secondDataset.relevance_explanation, "independent", "second")] : []),
    ...(evidence[0]?.matched_columns.includes("studytime") ? [relation("study-studytime", independent, "studytime", "verified variable mapping", evidence[0].notes[0], "independent", "variable")] : []),
    ...(evidence[1]?.matched_columns.includes("G3") ? [relation("outcome-g3", outcome, "G3", "verified variable mapping", evidence[1].notes[0], "outcome", "grade")] : []),
  ];
  const nodes = [
    { key: "question", title: "Question", type: "research question" },
    { key: "independent", title: independent, type: "interpreted concept" },
    { key: "outcome", title: outcome, type: "interpreted concept" },
    ...(firstDataset ? [{ key: "first", title: firstDataset.dataset_id, type: "UCI dataset" }] : []),
    ...(secondDataset ? [{ key: "second", title: secondDataset.dataset_id, type: "UCI dataset" }] : []),
    ...(relations.some((item) => item.id === "study-studytime") ? [{ key: "variable", title: "studytime", type: "verified column" }] : []),
    ...(relations.some((item) => item.id === "outcome-g3") ? [{ key: "grade", title: "G3", type: "verified column" }] : []),
  ];
  return <section className="graph-page" aria-labelledby="graph-title"><div className="graph-heading"><div><p className="eyebrow">Research instrument / 04 — Graph</p><h1 id="graph-title">Graph</h1><p className="section-deck">An evidence map of this cached example. The relation list below is the complete readable version.</p></div><EvidenceTag label="Cached demo" explanation="Only cached UCI metadata and computed variable evidence are shown." /></div>
    <div className="graph-grid"><div className="graph-main"><div className="graph-canvas"><div className="graph-canvas-header"><span className="data-label">Fig. 02 / Evidence topology</span><span>Fixed diagram · no interaction</span></div><svg viewBox="0 0 960 400" role="img" aria-label="Static evidence topology; all relations are listed below" preserveAspectRatio="xMidYMid meet">
      <g className="graph-guides" aria-hidden="true"><path d="M 0 200 H 960 M 320 0 V 400 M 600 0 V 400" /></g>
      {relations.map((edge) => <line key={edge.id} data-edge-id={edge.id} x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2} className={edge.label === "verified variable mapping" ? "verified-edge" : "metadata-edge"} />)}
      {nodes.map((node) => { const [x, y] = coordinates[node.key as keyof typeof coordinates]; return <g key={node.key} transform={`translate(${x},${y})`}><circle r="9" className={node.type === "verified column" ? "verified-node" : "ordinary-node"} /><text x="0" y="-22" textAnchor="middle">{node.title}</text><text x="0" y="32" textAnchor="middle" className="node-type">{node.type}</text></g>; })}
    </svg><div className="graph-legend"><span><i className="legend-dot" /> Evidence node</span><span><i className="legend-line" /> Documented relation</span><span><i className="legend-line verified" /> Verified column mapping</span></div></div>
    <section className="relation-section" aria-labelledby="relation-title"><div className="relation-heading"><span className="data-label">Evidence list / complete equivalent</span><h2 id="relation-title">Relations</h2></div><ol className="relation-list">{relations.map((edge) => <li key={edge.id} data-relation-id={edge.id}><div><strong>{edge.from} → {edge.to}</strong><span className="data-label">{edge.label}</span></div><p>{edge.source}</p></li>)}</ol></section></div>
    <aside className="graph-inspector"><span className="data-label">Inspector / selected example</span><h2>Study time → studytime</h2><p>{evidence[0]?.notes[0] ?? "No verified mapping available."}</p><EvidenceTag label="Computed profile" explanation="Research variable mapping is documented in the cached analysis profile." /><div className="publication-empty"><span className="data-label">Publication layer</span><p>No verified publication links are available.</p></div></aside></div>
  </section>;
}
