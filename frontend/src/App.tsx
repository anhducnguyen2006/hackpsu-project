import { FormEvent, useState } from "react";
import type { DatasetCardData, DiscoveryResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function searchDatasets(question: string): Promise<DiscoveryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/discovery/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ research_question: question, limit: 8 }),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Search failed (${response.status}).`);
  }
  return response.json() as Promise<DiscoveryResponse>;
}

function DatasetCard({
  dataset,
  expanded,
  onToggle,
}: {
  dataset: DatasetCardData;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <article className="dataset-card" onClick={onToggle}>
      <div className="card-content">
        <p className="card-source">{dataset.source}</p>
        <h3>{dataset.title}</h3>
        <p>{dataset.description ?? "No description was provided by UCI."}</p>
        <div className="card-tags">
          <span className="status-pill">Metadata-based assessment</span>
          <span className="status-pill">
            {dataset.preliminary_relevance_score === null
              ? "Score unavailable"
              : `Preliminary relevance: ${dataset.preliminary_relevance_score}/100`}
          </span>
        </div>
      </div>
      <button
        className="secondary-button"
        onClick={(event) => {
          event.stopPropagation();
          onToggle();
        }}
        type="button"
      >
        {expanded ? "Hide details" : "Details"}
      </button>
      {expanded && (
        <div className="details-panel">
          <p>{dataset.relevance_explanation}</p>
          <dl className="metadata-list">
            <div><dt>Dataset ID</dt><dd>{dataset.dataset_id}</dd></div>
            <div><dt>Subject area</dt><dd>{dataset.subject_area ?? "Not documented"}</dd></div>
            <div><dt>Instances</dt><dd>{dataset.instance_count ?? "Not documented"}</dd></div>
            <div><dt>Features</dt><dd>{dataset.feature_count ?? "Not documented"}</dd></div>
            <div><dt>Variables</dt><dd>{dataset.variables.length ? dataset.variables.join(", ") : "Not documented"}</dd></div>
            <div><dt>Data status</dt><dd>{dataset.data_status}</dd></div>
          </dl>
          <a href={dataset.repository_url} target="_blank" rel="noreferrer">
            View original UCI repository page
          </a>
        </div>
      )}
    </article>
  );
}

function App() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<DiscoveryResponse | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setExpanded(null);
    setLoading(true);
    try {
      setResult(await searchDatasets(question));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="hero">
        <p className="eyebrow">AI-assisted research workflow</p>
        <h1>Research Dataset Discovery</h1>
        <p className="subtitle">
          Find real datasets and understand whether they can support your research question.
        </p>
      </header>
      <form className="search-panel" onSubmit={handleSubmit}>
        <label htmlFor="research-question">Research question</label>
        <div className="search-row">
          <input
            id="research-question"
            value={question}
            minLength={10}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. Is study time associated with academic performance?"
            required
          />
          <button type="submit" disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>
      <section className="results" aria-live="polite">
        <div className="section-heading">
          <h2>Datasets</h2>
          <span className="status-pill">Verified UCI source</span>
        </div>
        {loading && <p className="empty-state">Interpreting your question and searching UCI...</p>}
        {error && <p className="error-state">{error}</p>}
        {!loading && !error && !result && (
          <p className="empty-state">Enter a research question to see verified dataset results.</p>
        )}
        {!loading && result && (
          <>
            <p className="processing-indicator">
              {result.processing_mode === "gemini"
                ? "AI-assessed with Gemini"
                : result.processing_mode === "partial_gemini"
                  ? "Gemini interpretation only; metadata fallback ranking"
                  : "Keyword-ranked fallback; Gemini was unavailable"}
            </p>
            {result.warnings.map((warning) => <p className="warning-state" key={warning}>{warning}</p>)}
            <p className="result-explanation">{result.explanation}</p>
            {result.datasets.length === 0 ? (
              <p className="empty-state">No relevant UCI datasets were found for this question.</p>
            ) : (
              result.datasets.map((dataset) => (
                <DatasetCard
                  dataset={dataset}
                  expanded={expanded === dataset.dataset_id}
                  key={dataset.dataset_id}
                  onToggle={() => setExpanded(expanded === dataset.dataset_id ? null : dataset.dataset_id)}
                />
              ))
            )}
          </>
        )}
      </section>
    </main>
  );
}

export default App;
