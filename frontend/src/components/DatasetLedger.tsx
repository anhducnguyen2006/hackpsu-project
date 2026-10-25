import { useState } from "react";
import type { DatasetCardData } from "../types";
import { EvidenceTag } from "./EvidenceTag";

function documented(value: number | null) { return value === null ? "Not documented" : value.toLocaleString(); }

export function DatasetLedger({ datasets, onOpenAnalysis }: { datasets: DatasetCardData[]; onOpenAnalysis: (datasetId: string) => void }) {
  const [expanded, setExpanded] = useState<string[]>([]);
  return <section className="workspace-grid ledger-page" aria-labelledby="datasets-title">
    <div className="workspace-content"><p className="eyebrow">Research instrument / 03 — Datasets</p><h1 id="datasets-title">Datasets</h1><p className="section-deck">Two cached UCI records surfaced from metadata. Relevance is preliminary and based on documented terms.</p>
      <div className="ledger-list">{datasets.map((dataset, index) => {
        const open = expanded.includes(dataset.dataset_id);
        return <article className="ledger-row" key={dataset.dataset_id}>
          <span className="ledger-index"><span>0{index + 1}</span><br /><span>{dataset.dataset_id}</span></span>
          <div className="ledger-main"><EvidenceTag label="UCI metadata" explanation="Metadata copied from the UCI Machine Learning Repository cached example." /><h2>{dataset.title}</h2><p>{dataset.description ?? "Not documented"}</p>
            <a href={dataset.repository_url} target="_blank" rel="noreferrer">UCI source</a>
            <dl className="ledger-meta"><div><dt>Observed instances (metadata)</dt><dd>{documented(dataset.instance_count)}</dd></div><div><dt>Features (metadata)</dt><dd>{documented(dataset.feature_count)}</dd></div><div><dt>Subject area</dt><dd>{dataset.subject_area ?? "Not documented"}</dd></div><div><dt>Matched terms</dt><dd>{dataset.matched_research_variables?.join(", ") || "Not documented"}</dd></div><div><dt>Missing or unverified</dt><dd>{dataset.missing_or_unverified_variables?.join(", ") || "Not documented"}</dd></div><div><dt>Classification</dt><dd>{dataset.classification?.replace(/_/g, " ") ?? "Not documented"}</dd></div></dl>
            <div className="ledger-actions"><button type="button" className="secondary-action" aria-expanded={open} aria-controls={`details-${dataset.dataset_id.replace(":", "-")}`} aria-label={`Details for ${dataset.title}`} onClick={() => setExpanded((current) => open ? current.filter((id) => id !== dataset.dataset_id) : [...current, dataset.dataset_id])}>{open ? "Hide details" : "View details"}</button>{dataset.dataset_id === "uci:320" ? <button type="button" className="primary-action" onClick={() => onOpenAnalysis(dataset.dataset_id)}>Open analysis preview</button> : <button type="button" className="secondary-action" disabled>Analysis preview unavailable</button>}</div>
          </div>
          <aside className="ledger-score"><EvidenceTag label="Metadata-based relevance" explanation="Preliminary ranking from cached UCI metadata; not a suitability assessment." /><strong>{dataset.preliminary_relevance_score ?? "Unavailable"}</strong><p>Confidence: {dataset.score_confidence}</p><p>{dataset.relevance_explanation}</p><p className="muted">Suitability: Unavailable</p></aside>
          {open && <div className="ledger-details" id={`details-${dataset.dataset_id.replace(":", "-")}`}><span className="data-label">Documented variables</span><dl>{dataset.variables.map((variable) => <div key={variable}><dt>{variable}</dt><dd>{dataset.variable_descriptions?.[variable] ?? "Not documented"}</dd></div>)}</dl><p><span className="data-label">Original URL</span><br /><a href={dataset.repository_url} target="_blank" rel="noreferrer">{dataset.repository_url}</a></p></div>}
        </article>;
      })}</div>
    </div><aside className="context-rail"><p className="eyebrow">Reading guide</p><h2>Match ≠ fit</h2><p className="rail-note">A metadata match suggests a dataset to inspect. It does not verify comparability, causal effect, or research suitability.</p><div className="rail-block"><span className="data-label">Analysis coverage</span><p>Only Student Performance has a cached computed profile in this preview.</p></div></aside>
  </section>;
}
