import { useEffect, useState } from "react";
import type { AuthorizedFetch } from "../auth/api";
import { protectedRequestError } from "../auth/api";
import type { ResearchHistoryItem, ResearchSession, SavedAssessment, SavedDatasetMatch } from "../types";

function formatTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? "Timestamp unavailable" : date.toLocaleString();
}

function metadataText(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key];
  return typeof value === "string" || typeof value === "number" ? String(value) : null;
}

function DatasetMatch({ match, index }: { match: SavedDatasetMatch; index: number }) {
  const title = metadataText(match.metadata, "title") ?? "Saved dataset";
  const source = metadataText(match.metadata, "source");
  const url = metadataText(match.metadata, "landing_page_url") ?? metadataText(match.metadata, "repository_url");
  return <article className="saved-dataset"><div><span className="data-label">{match.rank === null ? `Match ${index + 1}` : `Rank ${match.rank}`}</span><h3>{title}</h3>{source && <p className="muted">{source}</p>}{match.explanation && <p>{match.explanation}</p>}{url && <a href={url} target="_blank" rel="noreferrer">Open verified source ↗</a>}</div><strong className="saved-dataset-score">{match.relevance_score === null ? "Score unavailable" : `Score ${match.relevance_score}`}</strong></article>;
}

function Assessment({ assessment, index }: { assessment: SavedAssessment; index: number }) {
  const summary = typeof assessment.assessment.overall_assessment === "string" ? assessment.assessment.overall_assessment : null;
  const score = assessment.suitability_score ?? (typeof assessment.assessment.final_score === "number" ? assessment.assessment.final_score : null);
  return <article className="saved-assessment" key={`${String(assessment.dataset_id)}-${index}`}><div><span className="data-label">Dataset {assessment.dataset_id}</span><h3>Persisted suitability assessment</h3>{summary && <p>{summary}</p>}{assessment.model && <p className="muted">Model: {assessment.model}{assessment.assessment_version ? ` · ${assessment.assessment_version}` : ""}</p>}</div><strong>{score === null ? "Score unavailable" : score}</strong></article>;
}

export function PastResearch({ apiBase, authorizedFetch, selectedQueryId, onSelectQuery, onOpenConnections }: { apiBase?: string; authorizedFetch?: AuthorizedFetch; selectedQueryId: number | null; onSelectQuery: (queryId: number | null) => void; onOpenConnections?: () => void }) {
  const [history, setHistory] = useState<ResearchHistoryItem[]>([]);
  const [selected, setSelected] = useState<ResearchSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");

  useEffect(() => {
    if (!apiBase) { setLoading(false); setError("Past research is unavailable until the backend is connected."); return; }
    if (!authorizedFetch) { setLoading(false); setHistory([]); setError("Log in to view your saved research."); return; }
    let active = true;
    setLoading(true); setError("");
    authorizedFetch(`${apiBase}/api/v1/research/history?limit=100`).then((response) => { if (!response.ok) throw new Error(protectedRequestError(response.status, "Past research could not be loaded right now.")); return response.json() as Promise<ResearchHistoryItem[]>; }).then((items) => { if (active) setHistory(items); }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Past research could not be loaded right now."); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [apiBase, authorizedFetch]);

  useEffect(() => {
    if (selectedQueryId === null || !apiBase || !authorizedFetch) { setSelected(null); return; }
    let active = true;
    setDetailLoading(true); setDetailError("");
    authorizedFetch(`${apiBase}/api/v1/research/${selectedQueryId}/session`).then((response) => { if (!response.ok) throw new Error(response.status === 404 ? "This saved research session no longer exists." : protectedRequestError(response.status, "The saved research session could not be loaded.")); return response.json() as Promise<ResearchSession>; }).then((item) => { if (active) setSelected(item); }).catch((cause) => { if (active) setDetailError(cause instanceof Error ? cause.message : "The saved research session could not be loaded."); }).finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [apiBase, authorizedFetch, selectedQueryId]);

  return <section className="history-page" aria-labelledby="history-title"><div className="history-masthead"><div><p className="eyebrow">Research instrument / archive</p><h1 id="history-title">Past research</h1><p className="section-deck">Return to saved questions and see the context preserved for each session.</p></div><div className="history-masthead-actions"><span className="evidence-tag">Persistent history</span>{onOpenConnections && <button type="button" className="primary-action" onClick={onOpenConnections}>Research Connections <span aria-hidden="true">↗</span></button>}</div></div>
    {loading && <p className="empty-state" role="status">Loading saved research…</p>}
    {!loading && error && <p className="error-state" role="alert">{error}</p>}
    {!loading && !error && history.length === 0 && <div className="empty-state" role="status"><h2>No saved research yet</h2><p>Questions saved after a live discovery will appear here.</p></div>}
    {!loading && !error && history.length > 0 && <div className="history-layout"><ol className="history-list">{history.map((item) => <li key={item.id}><button type="button" className={selectedQueryId === item.id ? "history-item history-item-active" : "history-item"} onClick={() => onSelectQuery(item.id)}><span className="history-item-index">{String(item.id).padStart(2, "0")}</span><span><strong>{item.question}</strong><small>{formatTimestamp(item.created_at)}</small></span></button></li>)}</ol><article className="history-detail" aria-live="polite">{detailLoading && <p role="status">Loading saved session…</p>}{!detailLoading && detailError && <p className="error-state" role="alert">{detailError}</p>}{!detailLoading && !detailError && selected && <><p className="eyebrow">Saved session / {selected.id}</p><h2>{selected.question}</h2><dl className="history-meta"><div><dt>Created</dt><dd>{formatTimestamp(selected.created_at)}</dd></div><div><dt>Normalized question</dt><dd>{selected.normalized_question || "Not available"}</dd></div></dl>{selected.datasets.length > 0 ? <section className="saved-session-section" aria-labelledby="saved-datasets-title"><div className="section-title-row"><div><span className="eyebrow">Persisted matches</span><h2 id="saved-datasets-title">Saved datasets</h2></div><span className="evidence-tag">Repository metadata</span></div><div className="saved-dataset-list">{selected.datasets.map((match, index) => <DatasetMatch key={`${selected.id}-dataset-${index}`} match={match} index={index} />)}</div></section> : <div className="history-notice"><strong>Saved dataset details are not available.</strong><p>This session has no persisted dataset matches in the current response.</p></div>}{selected.assessments.length > 0 ? <section className="saved-session-section" aria-labelledby="saved-assessments-title"><div className="section-title-row"><div><span className="eyebrow">Persisted interpretation</span><h2 id="saved-assessments-title">Available assessments</h2></div><span className="evidence-tag">Saved assessment</span></div><div className="saved-assessment-list">{selected.assessments.map((assessment, index) => <Assessment key={`${selected.id}-assessment-${index}`} assessment={assessment} index={index} />)}</div></section> : <div className="history-notice"><strong>Assessments unavailable.</strong><p>No persisted assessment was returned for this saved session.</p></div>}</>}</article></div>}
  </section>;
}
