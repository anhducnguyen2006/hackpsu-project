import { useState } from "react";
import type { AuthorizedFetch } from "../auth/api";
import { protectedRequestError } from "../auth/api";
import type { SimilarResearchItem } from "../types";

export function RelatedResearch({ apiBase, authorizedFetch, question, onOpenResearch }: { apiBase?: string; authorizedFetch?: AuthorizedFetch; question: string; onOpenResearch?: (queryId: number) => void }) {
  const [items, setItems] = useState<SimilarResearchItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  async function findRelated() {
    if (!apiBase) { setError("Related research is unavailable until the backend is connected."); setHasSearched(true); return; }
    if (!authorizedFetch) { setError("Log in to compare this question with your saved research."); setHasSearched(true); return; }
    if (!question.trim()) { setError("Enter a research question to find related work."); setHasSearched(true); return; }
    setLoading(true); setError(""); setHasSearched(true);
    try {
      const response = await authorizedFetch(`${apiBase}/api/v1/research/similar`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: question.trim() }) });
      if (!response.ok) throw new Error(protectedRequestError(response.status, "Related research could not be loaded right now."));
      setItems((await response.json()) as SimilarResearchItem[]);
    } catch (cause) {
      setItems([]); setError(cause instanceof Error ? cause.message : "Related research could not be loaded right now.");
    } finally { setLoading(false); }
  }

  return <section className="related-research" aria-labelledby="related-research-title">
    <div className="related-heading"><div><p className="eyebrow">Semantic memory</p><h2 id="related-research-title">Related research</h2></div><button type="button" className="secondary-action" onClick={findRelated} disabled={loading || !question.trim()}>{loading ? "Searching…" : "Find related work"}</button></div>
    <p className="related-intro">Past questions are ranked by embedding similarity. Similarity is a lead for review, not proof of identical research intent.</p>
    {loading && <p className="empty-state related-state" role="status">Looking across saved research…</p>}
    {!loading && error && <p className="error-state related-state" role="alert">{error}</p>}
    {!loading && !error && hasSearched && items.length === 0 && <p className="empty-state related-state" role="status">No saved research is semantically related to this question.</p>}
    {!loading && !error && items.length > 0 && <ol className="related-list">{items.slice(0, 5).map((item) => <li key={item.id}><button type="button" className="related-question" onClick={() => onOpenResearch?.(item.id)}><span>{item.question}</span><small>{new Date(item.created_at).toLocaleString()} · similarity {(item.similarity_score * 100).toFixed(1)}%</small></button></li>)}</ol>}
    {!hasSearched && !apiBase && <p className="related-unavailable">Connect the backend to search saved research.</p>}
  </section>;
}
