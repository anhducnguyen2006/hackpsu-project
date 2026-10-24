import { FormEvent, useRef, useState } from "react";
import type {
  DatasetAnalysisResponse,
  DatasetCardData,
  DiscoveryResponse,
  ExploratoryAnalysisResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
// Two bounded Gemini attempts can take up to roughly 34s per call, plus UCI I/O.
const REQUEST_TIMEOUT_MS = 90_000;

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  init.signal?.addEventListener("abort", abort, { once: true });
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
    init.signal?.removeEventListener("abort", abort);
  }
}

async function searchDatasets(question: string, signal?: AbortSignal): Promise<DiscoveryResponse> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/api/v1/discovery/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ research_question: question, limit: 8 }),
    signal,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Search failed (${response.status}).`);
  }
  return response.json() as Promise<DiscoveryResponse>;
}

async function analyzeDataset(
  datasetId: string,
  question: string,
): Promise<DatasetAnalysisResponse> {
  const response = await fetchWithTimeout(
    `${API_BASE_URL}/api/v1/datasets/${encodeURIComponent(datasetId)}/analyze`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ research_question: question }),
    },
  );
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Analysis failed (${response.status}).`);
  }

  return response.json() as Promise<DatasetAnalysisResponse>;
}

async function exploreDataset(
  datasetId: string,
  question: string,
  independentVariable: string,
  outcomeVariable: string,
): Promise<ExploratoryAnalysisResponse> {
  const response = await fetchWithTimeout(
    `${API_BASE_URL}/api/v1/datasets/${encodeURIComponent(datasetId)}/explore`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        research_question: question,
        independent_variable: independentVariable,
        outcome_variable: outcomeVariable,
      }),
    },
  );
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `Exploratory analysis failed (${response.status}).`);
  }
  return response.json() as Promise<ExploratoryAnalysisResponse>;
}

function DatasetCard({
  dataset,
  expanded,
  onToggle,
  analysis,
  analyzing,
  onAnalyze,
  exploratory,
  exploring,
  onExplore,
  compareSelected,
  onCompareToggle,
}: {
  dataset: DatasetCardData;
  expanded: boolean;
  onToggle: () => void;
  analysis: DatasetAnalysisResponse | undefined;
  analyzing: boolean;
  onAnalyze: () => void;
  exploratory: ExploratoryAnalysisResponse | undefined;
  exploring: boolean;
  onExplore: (independent: string, outcome: string) => void;
  compareSelected: boolean;
  onCompareToggle: () => void;
}) {
  const independent = analysis?.profile?.columns.find((column) =>
    column.research_roles.includes("independent"),
  );
  const outcome = analysis?.profile?.columns.find((column) =>
    column.research_roles.includes("outcome"),
  );
  return (
    <article className="dataset-card" onClick={onToggle}>
      <div className="card-content">
        <label className="compare-control" onClick={(event) => event.stopPropagation()}>
          <input
            aria-label={`Select ${dataset.title} for comparison`}
            checked={compareSelected}
            onChange={onCompareToggle}
            type="checkbox"
          />
          Compare
        </label>
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
          <button
            className="analyze-button"
            disabled={analyzing}
            onClick={(event) => {
              event.stopPropagation();
              onAnalyze();
            }}
            type="button"
          >
            {analyzing ? "Analyzing dataset..." : "Analyze Dataset"}
          </button>
          {analysis && <AnalysisReport analysis={analysis} />}
          {analysis && independent && outcome && (
            <section className="explore-panel">
              <h5>Exploratory analysis</h5>
              <p className="report-label">
                Descriptive group summaries computed by Pandas; this does not establish causation.
              </p>
              <button
                className="secondary-button"
                disabled={exploring}
                onClick={(event) => {
                  event.stopPropagation();
                  onExplore(independent.name, outcome.name);
                }}
                type="button"
              >
                {exploring ? "Calculating..." : `Compare ${independent.name} with ${outcome.name}`}
              </button>
              {exploratory && <ExploratoryReport analysis={exploratory} />}
            </section>
          )}
        </div>
      )}
    </article>
  );
}

function ExploratoryReport({ analysis }: { analysis: ExploratoryAnalysisResponse }) {
  const maxMean = Math.max(...analysis.categories.map((item) => item.mean_outcome ?? 0), 1);
  return (
    <div className="exploratory-report">
      <p>
        {analysis.analyzed_observation_count} observations included;{" "}
        {analysis.excluded_observation_count} excluded due to missing values.
      </p>
      <div className="bar-chart" aria-label="Mean outcome by category">
        {analysis.categories.map((item) => (
          <div className="bar-group" key={String(item.category)}>
            <div
              className="bar"
              style={{ height: `${Math.max(((item.mean_outcome ?? 0) / maxMean) * 100, 4)}%` }}
              title={`Mean: ${item.mean_outcome ?? "Unavailable"}`}
            />
            <strong>{String(item.category)}</strong>
            <span>{item.mean_outcome ?? "—"} mean</span>
            <span>n={item.observations}</span>
          </div>
        ))}
      </div>
      <ul>
        {analysis.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
      </ul>
    </div>
  );
}

function AnalysisReport({ analysis }: { analysis: DatasetAnalysisResponse }) {
  const [showAllColumns, setShowAllColumns] = useState(false);
  const columns = [...analysis.profile!.columns].sort((left, right) => {
    const roleRank = (column: typeof left) =>
      column.research_roles.includes("outcome")
        ? 0
        : column.research_roles.includes("independent")
          ? 1
          : 2;
    return roleRank(left) - roleRank(right) || left.name.localeCompare(right.name);
  });
  return (
    <div className="analysis-report">
      {analysis.warnings.map((warning) => (
        <p className="warning-state" key={warning}>{warning}</p>
      ))}
      {analysis.profile ? (
        <>
          <div className="report-heading">
            <h4>Research suitability</h4>
            <span className="score-badge">
              {analysis.assessment?.final_score === null ||
              analysis.assessment?.final_score === undefined
                ? "Score unavailable"
                : `${analysis.assessment.final_score}/100`}
            </span>
          </div>
          <p className="report-label">
            {analysis.ai_assessment_status === "available"
              ? "AI assessment based on verified metadata and computed statistics"
              : "Statistical profile available; AI assessment unavailable"}
          </p>
          <p><strong>Profile:</strong> {analysis.profile.row_count} observed records, {analysis.profile.column_count} columns, {analysis.profile.duplicate_row_count} duplicate rows. Observed records are not necessarily independent participants.</p>
          {analysis.assessment && (
            <>
              <p>{analysis.assessment.overall_assessment}</p>
              <h5>Score breakdown</h5>
              <ul>
                {Object.entries(analysis.assessment.criteria).map(([name, criterion]) => (
                  <li key={name}>
                    <strong>{name.replace(/_/g, " ")}:</strong>{" "}
                    {criterion.score === null ? "Unknown" : `${criterion.score}/100`} — {criterion.explanation}
                  </li>
                ))}
              </ul>
              <h5>Limitations and next analyses</h5>
              <ul>
                {[...analysis.assessment.data_quality_issues, ...analysis.assessment.population_limitations, ...analysis.assessment.recommended_further_analyses].map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <p className="score-explanation">{analysis.assessment.score_explanation}</p>
            </>
          )}
          <h5>Research-variable evidence</h5>
          <ul>
            {analysis.profile.research_variable_evidence.map((item) => (
              <li key={item.research_variable}>
                <strong>{item.research_variable}:</strong>{" "}
                {item.matched_columns.length ? item.matched_columns.join(", ") : "no verified matching column"};{" "}
                {item.usable_observations} usable observations.
                {item.notes.length ? ` ${item.notes.join(" ")}` : ""}
              </li>
            ))}
          </ul>
          <h5>Statistics</h5>
          <p className="report-label">
            Relevant outcome and independent variables are shown first. Ordinal or encoded numeric variables show category frequencies; their means are not interpreted as exact units.
          </p>
          <div className="stats-grid">
            {(showAllColumns ? columns : columns.slice(0, 12)).map((column) => (
              <div className="stat-card" key={column.name}>
                <strong>{column.name}</strong>
                {column.research_roles.length > 0 && (
                  <span className="relevant-marker">
                    Relevant {column.research_roles.join(" + ")}
                  </span>
                )}
                <span>{column.measurement_type}</span>
                {column.measurement_type === "ordinal_or_encoded_numeric" ? (
                  <span>
                    Categories: {column.categorical_summary.map((item) => `${String(item.value)} (${item.count})`).join(", ")}
                  </span>
                ) : column.numeric_summary ? (
                  <span>Mean {column.numeric_summary.mean ?? "—"}; median {column.numeric_summary.median ?? "—"}</span>
                ) : (
                  <span>{column.unique_count} unique categories</span>
                )}
                <span>{column.missing_count} missing ({(column.missing_fraction * 100).toFixed(1)}%)</span>
              </div>
            ))}
          </div>
          {analysis.profile.columns.length > 12 && (
            <button
              className="secondary-button columns-button"
              onClick={() => setShowAllColumns((current) => !current)}
              type="button"
            >
              {showAllColumns ? "Show fewer columns" : `Show all ${analysis.profile.columns.length} columns`}
            </button>
          )}
        </>
      ) : (
        <p>Verified metadata is available, but the tabular data could not be analyzed.</p>
      )}
    </div>
  );
}

function ComparisonView({
  datasets,
  analyses,
  onClose,
}: {
  datasets: DatasetCardData[];
  analyses: Record<string, DatasetAnalysisResponse>;
  onClose: () => void;
}) {
  return (
    <section className="comparison-view">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Evidence comparison</p>
          <h3>Compare selected datasets</h3>
        </div>
        <button className="secondary-button" onClick={onClose} type="button">Close</button>
      </div>
      <div className="comparison-grid">
        {datasets.map((dataset) => {
          const analysis = analyses[dataset.dataset_id];
          const assessment = analysis?.assessment;
          const profile = analysis?.profile;
          return (
            <article className="comparison-card" key={dataset.dataset_id}>
              <h4>{dataset.title}</h4>
              <a href={dataset.repository_url} target="_blank" rel="noreferrer">Original source</a>
              <dl className="metadata-list">
                <div><dt>Preliminary relevance</dt><dd>{dataset.preliminary_relevance_score ?? "Unavailable"}</dd></div>
                <div><dt>Research suitability</dt><dd>{assessment?.final_score ?? "Not analyzed"}</dd></div>
                <div><dt>Records / columns</dt><dd>{profile ? `${profile.row_count} / ${profile.column_count}` : "Not analyzed"}</dd></div>
                <div><dt>Data status</dt><dd>{profile ? "Fully analyzed" : "Metadata only"}</dd></div>
              </dl>
              <h5>Relevant variables</h5>
              <p>
                Independent: {assessment?.relevant_independent_variables.join(", ") || "Unavailable"}<br />
                Outcomes: {assessment?.relevant_outcome_variables.join(", ") || "Unavailable"}
              </p>
              <h5>Missing evidence and limitations</h5>
              <ul>
                {(assessment
                  ? [...assessment.missing_or_unverified_research_variables, ...assessment.data_quality_issues, ...assessment.population_limitations]
                  : ["Analyze this dataset to compute statistics and assess limitations."]
                ).map((item) => <li key={item}>{item}</li>)}
              </ul>
              {assessment && (
                <>
                  <h5>Scoring criteria</h5>
                  <ul>
                    {Object.entries(assessment.criteria).map(([name, criterion]) => (
                      <li key={name}>{name.replace(/_/g, " ")}: {criterion.score ?? "Unknown"}/100</li>
                    ))}
                  </ul>
                </>
              )}
            </article>
          );
        })}
      </div>
      <p className="report-label">
        Comparison is evidence-based, not a guarantee that the highest score is the best scientific choice.
        Gemini comparative interpretation is unavailable until a dedicated comparative assessment is added.
      </p>
    </section>
  );
}

function App() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<DiscoveryResponse | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyses, setAnalyses] = useState<Record<string, DatasetAnalysisResponse>>({});
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [exploratory, setExploratory] = useState<Record<string, ExploratoryAnalysisResponse>>({});
  const [exploring, setExploring] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const searchSequence = useRef(0);
  const activeSearch = useRef<AbortController | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const sequence = ++searchSequence.current;
    activeSearch.current?.abort();
    const controller = new AbortController();
    activeSearch.current = controller;
    setError(null);
    setResult(null);
    setExpanded(null);
    setAnalyses({});
    setExploratory({});
    setSelected([]);
    setCompareOpen(false);
    setLoading(true);
    try {
      const nextResult = await searchDatasets(question, controller.signal);
      if (sequence === searchSequence.current) {
        setResult(nextResult);
      }
    } catch (requestError) {
      if (sequence !== searchSequence.current) return;
      setError(
        requestError instanceof DOMException && requestError.name === "AbortError"
          ? "Search timed out or was cancelled. Please retry."
          : requestError instanceof Error ? requestError.message : "Search failed.",
      );
    } finally {
      if (sequence === searchSequence.current) setLoading(false);
    }
  }

  async function handleAnalyze(dataset: DatasetCardData) {
    setAnalyzing(dataset.dataset_id);
    try {
      const analysis = await analyzeDataset(dataset.dataset_id, question);
      setAnalyses((current) => ({ ...current, [dataset.dataset_id]: analysis }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Analysis failed.");
    } finally {
      setAnalyzing(null);
    }
  }

  async function handleExplore(
    dataset: DatasetCardData,
    independentVariable: string,
    outcomeVariable: string,
  ) {
    setExploring(dataset.dataset_id);
    setError(null);
    try {
      const response = await exploreDataset(
        dataset.dataset_id,
        question,
        independentVariable,
        outcomeVariable,
      );
      setExploratory((current) => ({ ...current, [dataset.dataset_id]: response }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Exploratory analysis failed.");
    } finally {
      setExploring(null);
    }
  }

  function toggleSelected(datasetId: string) {
    setSelected((current) =>
      current.includes(datasetId)
        ? current.filter((id) => id !== datasetId)
        : current.length < 3 ? [...current, datasetId] : current,
    );
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
      <form className="search-panel" id="research-search" onSubmit={handleSubmit}>
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
        {error && (
          <div className="error-state">
            <p>{error}</p>
            <button type="submit" form="research-search">Retry search</button>
          </div>
        )}
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
            {selected.length >= 2 && (
              <button className="compare-action" onClick={() => setCompareOpen(true)} type="button">
                Compare selected ({selected.length})
              </button>
            )}
            {compareOpen && (
              <ComparisonView
                datasets={result.datasets.filter((dataset) => selected.includes(dataset.dataset_id))}
                analyses={analyses}
                onClose={() => setCompareOpen(false)}
              />
            )}
            {result.datasets.length === 0 ? (
              <p className="empty-state">No relevant UCI datasets were found for this question.</p>
            ) : (
              result.datasets.map((dataset) => (
                <DatasetCard
                  dataset={dataset}
                  expanded={expanded === dataset.dataset_id}
                  key={dataset.dataset_id}
                  onToggle={() => setExpanded(expanded === dataset.dataset_id ? null : dataset.dataset_id)}
                  analysis={analyses[dataset.dataset_id]}
                  analyzing={analyzing === dataset.dataset_id}
                  onAnalyze={() => handleAnalyze(dataset)}
                  exploratory={exploratory[dataset.dataset_id]}
                  exploring={exploring === dataset.dataset_id}
                  onExplore={(independent, outcome) => handleExplore(dataset, independent, outcome)}
                  compareSelected={selected.includes(dataset.dataset_id)}
                  onCompareToggle={() => toggleSelected(dataset.dataset_id)}
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
