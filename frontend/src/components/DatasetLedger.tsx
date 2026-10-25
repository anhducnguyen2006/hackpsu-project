import { useEffect, useMemo, useState } from "react";
import type { DatasetCardData, DatasetGraphResponse, DiscoveryResponse, DownloadResource } from "../types";
import { DatasetGraph } from "./DatasetGraph";
import { EvidenceTag } from "./EvidenceTag";

function sourceUrl(dataset: DatasetCardData) { return dataset.landing_page_url ?? dataset.repository_url; }
function scoreLabel(dataset: DatasetCardData) {
  if (dataset.semantic_similarity_score !== null && dataset.semantic_similarity_score !== undefined) return dataset.semantic_similarity_score.toFixed(2);
  if (dataset.preliminary_relevance_score !== null) return `${dataset.preliminary_relevance_score}`;
  return "Unavailable";
}
function formatBytes(size: number | null | undefined) {
  if (size === null || size === undefined) return "Size not documented";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
function joinOr(values: string[] | undefined, fallback: string) {
  return values && values.length ? values.join(", ") : fallback;
}
function resourceLabel(resource: DownloadResource) {
  const name = resource.filename ?? resource.original_filename ?? resource.file_id ?? "Unnamed file";
  return `${name} (${resource.format}; ${formatBytes(resource.size_bytes ?? null)}${resource.eligible ? "; eligible" : "; not verified for download"})`;
}
function variableCoverageLabel(dataset: DatasetCardData) {
  const matched = dataset.matched_research_variables ?? [];
  if (matched.length) return matched.join(", ");
  if (dataset.score_type === "semantic_similarity") {
    return "Unknown until analysis — topical similarity is not verified variable coverage";
  }
  return "Not documented";
}

export function DatasetLedger({ datasets, discovery, analysisMode = "preview", analysisLoading = false, analysisError = "", onOpenAnalysis, graph, graphLoading = false, graphError = "" }: { datasets: DatasetCardData[]; discovery?: DiscoveryResponse | null; analysisMode?: "preview" | "live"; analysisLoading?: boolean; analysisError?: string; onOpenAnalysis: (datasetId: string, resourceId?: string) => void; graph?: DatasetGraphResponse | null; graphLoading?: boolean; graphError?: string }) {
  const [expanded, setExpanded] = useState<string[]>([]);
  const [resourceChoice, setResourceChoice] = useState<Record<string, string>>({});
  const [source, setSource] = useState("all");
  const [sort, setSort] = useState<"semantic" | "original">("semantic");
  const [viewMode, setViewMode] = useState<"cards" | "graph">("cards");
  const datasetIds = datasets.map((dataset) => dataset.dataset_id).join("\n");
  useEffect(() => { setResourceChoice({}); }, [datasetIds]);
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
        const eligibleResources = (dataset.download_resources ?? []).filter((resource) => resource.eligible && (resource.file_id || resource.filename));
        const candidates = (dataset.verification_candidates ?? []).filter((resource) => resource.eligible !== true && (resource.file_id || resource.filename));
        const listedFiles = [
          ...(dataset.download_resources ?? []),
          ...candidates.filter((resource) => !(dataset.download_resources ?? []).some((item) => (item.file_id || item.filename) === (resource.file_id || resource.filename))),
        ];
        const resourceKey = (resource: (typeof eligibleResources)[number]) => resource.file_id || resource.filename || "";
        const chosenResource = resourceChoice[dataset.dataset_id] ?? "";
        const onlyResource = eligibleResources.length === 1 ? eligibleResources[0] : undefined;
        const isUci = dataset.dataset_id.startsWith("uci:");
        const selectedResourceId = isUci ? undefined : onlyResource ? resourceKey(onlyResource) : chosenResource || undefined;
        const canAnalyze = analysisMode === "preview" ? dataset.dataset_id === "uci:320" : isUci || Boolean(selectedResourceId);
        return <article className="ledger-row" key={dataset.dataset_id}>
          <span className="ledger-index"><span>{String(index + 1).padStart(2, "0")}</span><br /><span>{dataset.dataset_id}</span></span>
          <div className="ledger-main"><EvidenceTag label={dataset.source} explanation="Repository provenance supplied by the discovery response." /><h2>{dataset.title}</h2><p>{dataset.description ?? "Description unavailable."}</p>
            {url ? <a href={url} target="_blank" rel="noreferrer">{analysisMode === "preview" ? "UCI source" : "Original repository record"} <span aria-hidden="true">↗</span></a> : <span className="muted">Original repository URL unavailable</span>}
            <div className="card-tags" aria-label="Matched research concepts">{concepts.length ? concepts.map((match) => <span className="concept-tag" key={`${dataset.dataset_id}-${match.concept_id}`}>{match.concept}</span>) : <span className="muted">Matched concepts unavailable</span>}</div>
            <dl className="ledger-meta">{analysisMode === "live" && <div><dt>Available formats</dt><dd>{formats.length ? formats.join(", ") : "Unavailable"}</dd></div>}<div><dt>Observed instances</dt><dd>{dataset.instance_count === null || dataset.instance_count === undefined ? "Not documented" : dataset.instance_count.toLocaleString()}</dd></div><div><dt>Features</dt><dd>{dataset.feature_count === null || dataset.feature_count === undefined ? "Not documented" : dataset.feature_count.toLocaleString()}</dd></div><div><dt>Data status</dt><dd>{dataset.data_available === null ? "Unavailable" : dataset.data_available ? "Available" : "Not available"}</dd></div>{dataset.eligibility_status && <div><dt>Resource check</dt><dd>{dataset.eligibility_status.replace(/_/g, " ")}{dataset.download_performed ? "" : "; not downloaded"}</dd></div>}<div><dt>Subject area</dt><dd>{dataset.subject_area ?? dataset.subjects?.join(", ") ?? "Not documented"}</dd></div><div><dt>Matched variables</dt><dd>{variableCoverageLabel(dataset)}</dd></div><div><dt>Missing or unverified</dt><dd>{dataset.missing_or_unverified_variables?.join(", ") || (dataset.score_type === "semantic_similarity" ? "Variable presence not verified from metadata alone" : "Not documented")}</dd></div><div><dt>Classification</dt><dd>{dataset.classification?.replace(/_/g, " ") ?? "Not documented"}</dd></div></dl>
            <div className="ledger-actions">{analysisMode === "live" && eligibleResources.length > 1 && <label htmlFor={`file-${dataset.dataset_id.replace(/[^a-zA-Z0-9_-]/g, "-")}`}>Data file — pick one, then Analyze<select id={`file-${dataset.dataset_id.replace(/[^a-zA-Z0-9_-]/g, "-")}`} aria-label={`Data file for ${dataset.title}`} value={chosenResource} onChange={(event) => setResourceChoice((current) => ({ ...current, [dataset.dataset_id]: event.target.value }))}><option value="">Choose a data file</option>{eligibleResources.map((resource) => <option key={resourceKey(resource)} value={resourceKey(resource)}>{resource.filename ?? resource.file_id} ({resource.format})</option>)}</select></label>}<button type="button" className="secondary-action" aria-expanded={open} aria-controls={`details-${dataset.dataset_id.replace(":", "-")}`} aria-label={`Details for ${dataset.title}`} onClick={() => setExpanded((current) => open ? current.filter((id) => id !== dataset.dataset_id) : [...current, dataset.dataset_id])}>{open ? "Hide details" : "View details"}</button>{canAnalyze ? <button type="button" className="primary-action" onClick={() => selectedResourceId ? onOpenAnalysis(dataset.dataset_id, selectedResourceId) : onOpenAnalysis(dataset.dataset_id)}>{analysisLoading ? "Analyzing…" : analysisMode === "preview" ? "Open analysis preview" : "Analyze dataset"}</button> : analysisMode === "preview" ? <button type="button" className="secondary-action" disabled>Analysis preview unavailable</button> : eligibleResources.length > 1 ? <p className="muted" role="status">Select a data file in the dropdown above to enable Analyze.</p> : eligibleResources.length === 1 ? <button type="button" className="primary-action" onClick={() => onOpenAnalysis(dataset.dataset_id, resourceKey(eligibleResources[0]))}>{analysisLoading ? "Analyzing…" : "Analyze dataset"}</button> : <button type="button" className="secondary-action" disabled title="No supported public tabular file was verified for this dataset.">No supported data file</button>}{analysisMode === "live" && candidates.length > 0 && <div><p>Not verified. A filename alone is not a download-verified file.</p>{candidates.map((resource) => <button type="button" key={resource.file_id || resource.filename} onClick={() => onOpenAnalysis(dataset.dataset_id, resource.file_id || resource.filename || "")}>Check contents of {resource.filename ?? resource.file_id}</button>)}</div>}</div>
          </div>
          <aside className="ledger-score"><EvidenceTag label={dataset.score_type === "semantic_similarity" ? "Semantic similarity" : "Metadata-based relevance"} explanation="This ranks verified metadata against the research question. It is not a scientific suitability assessment." /><strong>{scoreLabel(dataset)}</strong><p>{dataset.score_type === "semantic_similarity" ? "Topical similarity to the question — not proof that required variables are present" : `Confidence: ${dataset.score_confidence}`}</p><p>{dataset.relevance_explanation}</p><p className="muted">Scientific suitability: Unavailable until analysis</p></aside>
          {open && <div className="ledger-details" id={`details-${dataset.dataset_id.replace(":", "-")}`}>
            <span className="data-label">Repository metadata</span>
            <dl>
              <div><dt>Title</dt><dd>{dataset.title}</dd></div>
              <div><dt>Description</dt><dd>{dataset.description ?? "Not documented"}</dd></div>
              <div><dt>Authors / creators</dt><dd>{joinOr(dataset.authors, "Not documented")}</dd></div>
              <div><dt>Publisher / repository</dt><dd>{dataset.publisher ?? dataset.source}</dd></div>
              <div><dt>Publication / release date</dt><dd>{dataset.publication_date ?? "Not documented"}</dd></div>
              <div><dt>Version</dt><dd>{dataset.source_version ?? "Not documented"}</dd></div>
              <div><dt>Subjects</dt><dd>{joinOr(dataset.subjects, dataset.subject_area ?? "Not documented")}</dd></div>
              <div><dt>Keywords</dt><dd>{joinOr(dataset.keywords, "Not documented")}</dd></div>
              <div><dt>License / access</dt><dd>{dataset.license ?? "Not documented"}</dd></div>
              <div><dt>Geographic coverage</dt><dd>{joinOr(dataset.geographic_coverage, "Not documented")}</dd></div>
              <div><dt>Temporal coverage</dt><dd>{joinOr(dataset.temporal_coverage, "Not documented")}</dd></div>
              <div><dt>DOI</dt><dd>{dataset.doi ? <a href={dataset.doi.startsWith("http") ? dataset.doi : `https://doi.org/${dataset.doi.replace(/^doi:/i, "")}`} target="_blank" rel="noreferrer">{dataset.doi}</a> : "Not documented"}</dd></div>
              <div><dt>Official source</dt><dd>{url ? <a href={url} target="_blank" rel="noreferrer">{url}</a> : "Unavailable"}</dd></div>
              <div><dt>Observed instances</dt><dd>{dataset.instance_count === null || dataset.instance_count === undefined ? "Not documented by repository metadata" : dataset.instance_count.toLocaleString()}</dd></div>
              <div><dt>Feature / column count</dt><dd>{dataset.feature_count === null || dataset.feature_count === undefined ? "Not documented by repository metadata" : dataset.feature_count.toLocaleString()}</dd></div>
            </dl>
            <span className="data-label">Published data files</span>
            {listedFiles.length ? <ul>{listedFiles.map((resource) => <li key={`${resource.file_id || ""}-${resource.filename || ""}-${resource.url}`}>{resourceLabel(resource)}{resource.checksum ? `; checksum ${resource.checksum}` : ""}</li>)}</ul> : <p>No file inventory was included in the verified metadata response.</p>}
            <span className="data-label">Documented variables</span>
            {dataset.variables.length ? <dl>{dataset.variables.map((variable) => <div key={variable}><dt>{variable}</dt><dd>{dataset.variable_descriptions?.[variable] ?? "Not documented"}</dd></div>)}</dl> : <p>Repository metadata did not document variable names. Row/column evidence appears only after a successful file analysis.</p>}
          </div>}
        </article>;
      })}</div>}
      </div>
    </div><aside className="context-rail"><p className="eyebrow">Reading guide</p><h2>Match ≠ fit</h2><p className="rail-note">Semantic similarity is topical overlap with the research question. It does not verify that caffeine, sleep quality, or other required variables are present. Suitability is assessed only after a file is analyzed.</p><div className="rail-block"><span className="data-label">Analysis coverage</span><p>{analysisMode === "live" ? "Choose one public tabular file. The server downloads that file and computes the profile. Unverified filenames stay unverified until the file is parsed." : "Only Student Performance has a cached computed profile in this preview."}</p></div></aside>
  </section>;
}
