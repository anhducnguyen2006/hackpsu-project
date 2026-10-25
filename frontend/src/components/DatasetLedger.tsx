import { useMemo, useState } from "react";
import type { DatasetCardData, DatasetGraphResponse, DiscoveryResponse } from "../types";
import { DatasetGraph } from "./DatasetGraph";
import { EvidenceTag } from "./EvidenceTag";

function sourceUrl(dataset: DatasetCardData) { return dataset.landing_page_url ?? dataset.repository_url; }
function scoreLabel(dataset: DatasetCardData) {
  if (dataset.semantic_similarity_score !== null && dataset.semantic_similarity_score !== undefined) return `${(dataset.semantic_similarity_score * 100).toFixed(1)}%`;
  if (dataset.preliminary_relevance_score !== null) return `${dataset.preliminary_relevance_score}`;
  return "Unavailable";
}

export function DatasetLedger({ datasets, discovery, analysisMode = "preview", analysisLoading = false, analysisError = "", onOpenAnalysis, graph, graphLoading = false, graphError = "" }: { datasets: DatasetCardData[]; discovery?: DiscoveryResponse | null; analysisMode?: "preview" | "live"; analysisLoading?: boolean; analysisError?: string; onOpenAnalysis: (datasetId: string) => void; graph?: DatasetGraphResponse | null; graphLoading?: boolean; graphError?: string }) {
  const [expanded, setExpanded] = useState<string[]>([]);
  const [source, setSource] = useState("all");
  const [sort, setSort] = useState<"semantic" | "original">("semantic");
  const [viewMode, setViewMode] = useState<"cards" | "graph">("cards");
  const sources = useMemo(() => [...new Set(datasets.map((dataset) => dataset.source))].sort(), [datasets]);
  const visible = useMemo(() => datasets.filter((dataset) => source === "all" || dataset.source === source).sort((a, b) => sort === "semantic" ? (b.semantic_similarity_score ?? -1) - (a.semantic_similarity_score ?? -1) : 0), [datasets, source, sort]);
  const partial = discovery?.warnings?.length;
  return <section className="workspace-grid ledger-page" aria-labelledby="datasets-title">
    <div className="workspace-content"><p className="eyebrow">Research instrument / 03 — Datasets</p><h1 id="datasets-title">Datasets</h1><p className="section-deck">{discovery ? discovery.explanation : "Two cached UCI records surfaced from metadata. Relevance is preliminary and based on documented terms."}</p>
      <div className="view-toggle" aria-label="Dataset result view"><span className="data-label">View</span><div role="group" aria-label="Choose dataset view"><button type="button" className={viewMode === "cards" ? "view-toggle-active" : ""} aria-pressed={viewMode === "cards"} onClick={() => setViewMode("cards")}>Cards</button><button type="button" className={viewMode === "graph" ? "view-toggle-active" : ""} aria-pressed={viewMode === "graph"} onClick={() => setViewMode("graph")}>Graph view</button></div></div>
      <div hidden={viewMode !== "graph"}><DatasetGraph graph={graph ?? null} datasets={datasets} loading={graphLoading} error={graphError} /></div><div hidden={viewMode !== "cards"}>
      {discovery && <div className="ledger-controls" aria-label="Dataset result controls"><label htmlFor="source-filter">Source repository<select id="source-filter" value={source} onChange={(event) => setSource(event.target.value)}><option value="all">All repositories</option>{sources.map((item) => <option key={item} value={item}>{item}</option>)}</select></label><label htmlFor="dataset-sort">Sort results<select id="dataset-sort" value={sort} onChange={(event) => setSort(event.target.value as "semantic" | "original")}><option value="semantic">Semantic similarity</option><option value="original">Original result order</option></select></label></div>}
      {partial ? <p className="warning-state" role="status">Some repository sources were unavailable. Results below are partial; inspect the source labels and warnings before drawing conclusions.</p> : null}
      {analysisError ? <p className="warning-state" role="alert">{analysisError} Retry from the dataset row.</p> : null}
      {visible.length === 0 ? <div className="empty-state" role="status"><h2>No datasets found</h2><p>{datasets.length ? "No results match the selected repository filter." : "No verified dataset metadata matched this research question."}</p></div> : <div className="ledger-list">{visible.map((dataset, index) => {
        const open = expanded.includes(dataset.dataset_id);
        const url = sourceUrl(dataset);
        const concepts = dataset.concept_matches ?? [];
        const formats = [...new Set((dataset.download_resources ?? []).map((resource) => resource.format))];
        const canAnalyze = dataset.dataset_id.startsWith("uci:") && (analysisMode === "live" || dataset.dataset_id === "uci:320");
        return <article className="ledger-row" key={dataset.dataset_id}>
          <span className="ledger-index"><span>{String(index + 1).padStart(2, "0")}</span><br /><span>{dataset.dataset_id}</span></span>
          <div className="ledger-main"><EvidenceTag label={dataset.source} explanation="Repository provenance supplied by the discovery response." /><h2>{dataset.title}</h2><p>{dataset.description ?? "Description unavailable."}</p>
            {url ? <a href={url} target="_blank" rel="noreferrer">{analysisMode === "preview" ? "UCI source" : "Original repository record"} <span aria-hidden="true">↗</span></a> : <span className="muted">Original repository URL unavailable</span>}
            <div className="card-tags" aria-label="Matched research concepts">{concepts.length ? concepts.map((match) => <span className="concept-tag" key={`${dataset.dataset_id}-${match.concept_id}`}>{match.concept}</span>) : <span className="muted">Matched concepts unavailable</span>}</div>
            <dl className="ledger-meta">{analysisMode === "live" && <div><dt>Available formats</dt><dd>{formats.length ? formats.join(", ") : "Unavailable"}</dd></div>}<div><dt>Observed instances</dt><dd>{dataset.instance_count === null ? "Not documented" : dataset.instance_count.toLocaleString()}</dd></div><div><dt>Features</dt><dd>{dataset.feature_count === null ? "Not documented" : dataset.feature_count.toLocaleString()}</dd></div><div><dt>Data status</dt><dd>{dataset.data_available === null ? "Unavailable" : dataset.data_available ? "Available" : "Not available"}</dd></div><div><dt>Subject area</dt><dd>{dataset.subject_area ?? dataset.subjects?.join(", ") ?? "Not documented"}</dd></div><div><dt>Matched variables</dt><dd>{dataset.matched_research_variables?.join(", ") || "Not documented"}</dd></div><div><dt>Missing or unverified</dt><dd>{dataset.missing_or_unverified_variables?.join(", ") || "Not documented"}</dd></div><div><dt>Classification</dt><dd>{dataset.classification?.replace(/_/g, " ") ?? "Not documented"}</dd></div></dl>
            <div className="ledger-actions"><button type="button" className="secondary-action" aria-expanded={open} aria-controls={`details-${dataset.dataset_id.replace(":", "-")}`} aria-label={`Details for ${dataset.title}`} onClick={() => setExpanded((current) => open ? current.filter((id) => id !== dataset.dataset_id) : [...current, dataset.dataset_id])}>{open ? "Hide details" : "View details"}</button>{canAnalyze ? <button type="button" className="primary-action" disabled={analysisLoading} onClick={() => onOpenAnalysis(dataset.dataset_id)}>{analysisLoading ? "Analyzing…" : analysisMode === "preview" ? "Open analysis preview" : "Analyze UCI dataset"}</button> : <button type="button" className="secondary-action" disabled title="Analysis currently supports UCI datasets only">{analysisMode === "preview" ? "Analysis preview unavailable" : "UCI analysis only"}</button>}</div>
          </div>
          <aside className="ledger-score"><EvidenceTag label={dataset.score_type === "semantic_similarity" ? "Semantic similarity" : "Metadata-based relevance"} explanation="This ranks verified metadata against the research question. It is not a scientific suitability assessment." /><strong>{scoreLabel(dataset)}</strong><p>{dataset.score_type === "semantic_similarity" ? "Similarity to question and concepts" : `Confidence: ${dataset.score_confidence}`}</p><p>{dataset.relevance_explanation}</p><p className="muted">Scientific suitability: Unavailable</p></aside>
          {open && <div className="ledger-details" id={`details-${dataset.dataset_id.replace(":", "-")}`}><span className="data-label">Verified variable metadata</span><dl>{dataset.variables.map((variable) => <div key={variable}><dt>{variable}</dt><dd>{dataset.variable_descriptions?.[variable] ?? "Not documented"}</dd></div>)}</dl><p><span className="data-label">Original URL</span><br />{url ? <a href={url} target="_blank" rel="noreferrer">{url}</a> : "Unavailable"}</p>{dataset.doi && <p><span className="data-label">DOI</span><br />{dataset.doi}</p>}</div>}
        </article>;
      })}</div>}
      </div>
    </div><aside className="context-rail"><p className="eyebrow">Reading guide</p><h2>Match ≠ fit</h2><p className="rail-note">A metadata match suggests a dataset to inspect. It does not verify comparability, causal effect, or research suitability.</p><div className="rail-block"><span className="data-label">Analysis coverage</span><p>{analysisMode === "live" ? "Only UCI datasets can currently load the existing analysis service. Other repositories remain browseable metadata records." : "Only Student Performance has a cached computed profile in this preview."}</p></div></aside>
  </section>;
}
