import { ThemeToggle } from "./components/ThemeToggle";
import type { ReactNode } from "react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { ResearchQuestion } from "./components/ResearchQuestion";
import { EXAMPLE_QUESTION } from "./demo/researchExample";
import { EXAMPLE_INTERPRETATION } from "./demo/researchExample";
import { InterpretationSheet } from "./components/InterpretationSheet";
import { DatasetLedger } from "./components/DatasetLedger";
import { EXAMPLE_DATASETS } from "./demo/researchExample";
import { EXAMPLE_ANALYSIS } from "./demo/researchExample";
import { newSession } from "./graph/graphSession";
const DatasetGraph = lazy(() => import("./components/DatasetGraph").then(m => ({default:m.DatasetGraph})));
import { AnalysisView } from "./components/AnalysisView";
import { EXAMPLE_EXPLORATION } from "./demo/researchExample";
import { PastResearch } from "./components/PastResearch";
import type { DatasetAnalysisResponse, DatasetGraphResponse, DiscoveryResponse, ExploratoryAnalysisResponse } from "./types";
import { ResearchConnectionsGraph } from "./components/ResearchConnectionsGraph";

export type PreviewStage = "question" | "interpretation" | "datasets" | "graph" | "analysis" | "history" | "connections";
const stages: { key: PreviewStage; label: string }[] = [
  { key: "question", label: "Question" }, { key: "interpretation", label: "Interpretation" },
  { key: "datasets", label: "Datasets" }, { key: "graph", label: "Graph" },
  { key: "analysis", label: "Analysis" }, { key: "connections", label: "Research graph" },
  { key: "history", label: "Past Research" },
];

function getApiBase(): string | undefined {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  return import.meta.env.MODE === "test" ? undefined : "http://localhost:8000";
}

function App({ authControls }: { authControls?: ReactNode }) {
  const [stage, setStage] = useState<PreviewStage>("question");
  const [discovery, setDiscovery] = useState<DiscoveryResponse | null>(null);
  const [activeQuestion, setActiveQuestion] = useState(EXAMPLE_QUESTION);
  const [analysis, setAnalysis] = useState<DatasetAnalysisResponse | null>(EXAMPLE_ANALYSIS);
  const [exploration, setExploration] = useState<ExploratoryAnalysisResponse | undefined>(EXAMPLE_EXPLORATION);
  const [analysisMode, setAnalysisMode] = useState<"preview" | "live">("preview");
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [graph, setGraph] = useState<DatasetGraphResponse | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState("");
  const [selectedQueryId, setSelectedQueryId] = useState<number | null>(null);
  const requestSequence = useRef(0);
  const searchController = useRef<AbortController | null>(null);
  const analysisController = useRef<AbortController | null>(null);
  const analysisSequence = useRef(0);
  const graphSequence = useRef(0);
  const graphSession = useRef(newSession());
  const navigationSequence = useRef(0);
  function navigate(next: PreviewStage) { navigationSequence.current++; setStage(next); }
  useEffect(() => () => { searchController.current?.abort(); analysisController.current?.abort(); }, []);
  const apiBase = getApiBase();
  const liveSearchEnabled = Boolean(apiBase);
  function openResearch(queryId: number) {
    setSelectedQueryId(queryId);
    navigate("history");
  }
  function openConnections() {
    navigate("connections");
  }
  async function search(question: string) {
    if (!apiBase) throw new Error("Live search is not configured for this frontend.");
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    const sequence = ++requestSequence.current;
    analysisController.current?.abort();
    analysisSequence.current++;
    setAnalysisLoading(false);
    graphSession.current = newSession();
    const navigationAtStart = navigationSequence.current;
    setDiscovery(null);
    setActiveQuestion(question);
    setAnalysisMode("live");
    setAnalysis(null);
    setExploration(undefined);
    setAnalysisError("");
    setGraph(null);
    setGraphError("");
    setGraphLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/v1/discovery/search`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: question, limit: 12 }), signal: controller.signal });
      if (!response.ok) throw new Error("The discovery service could not complete this search. Check that the backend is running and try again.");
      const payload = await response.json() as DiscoveryResponse;
      if (sequence !== requestSequence.current) return;
      setDiscovery(payload);
      if (navigationAtStart === navigationSequence.current) setStage("interpretation");
      await loadGraph(question, sequence, controller.signal);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (sequence === requestSequence.current) setGraphLoading(false);
      throw error;
    }
  }
  async function loadGraph(question: string, generation: number, signal?: AbortSignal) {
    if (!apiBase) return;
    const revision = ++graphSequence.current;
    setGraphLoading(true); setGraphError("");
    try {
      const response = await fetch(`${apiBase}/api/v1/discovery/graph`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({research_question:question,limit:12}), signal});
      if (!response.ok) throw new Error("The dataset graph could not be loaded for this search.");
      const payload = await response.json() as DatasetGraphResponse;
      if (generation === requestSequence.current && revision === graphSequence.current) setGraph(payload);
    } catch (error) {
      if (signal?.aborted) return;
      if (generation === requestSequence.current && revision === graphSequence.current) setGraphError(error instanceof Error ? error.message : "Relationships unavailable.");
    } finally { if (generation === requestSequence.current && revision === graphSequence.current) setGraphLoading(false); }
  }
  async function openAnalysis(datasetId: string) {
    if (analysisMode === "preview") { if (datasetId === "uci:320") navigate("analysis"); return; }
    if (!datasetId.startsWith("uci:") || !apiBase || !discovery?.datasets.some(d=>d.dataset_id===datasetId)) return;
    analysisController.current?.abort();
    const controller = new AbortController(); analysisController.current = controller;
    const generation = requestSequence.current, request = ++analysisSequence.current, navigation = navigationSequence.current;
    setAnalysisLoading(true); setAnalysisError("");
    try {
      const response = await fetch(`${apiBase}/api/v1/datasets/${encodeURIComponent(datasetId)}/analyze`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({research_question:activeQuestion}),signal:controller.signal});
      if (!response.ok) {
        let detail = "UCI analysis is unavailable for this dataset right now.";
        try {
          const payload = await response.json() as { detail?: string };
          if (payload.detail) detail = payload.detail;
        } catch {
          // Keep the standard message when the server did not return JSON.
        }
        throw new Error(detail);
      }
      const payload = await response.json() as DatasetAnalysisResponse;
      if (generation !== requestSequence.current || request !== analysisSequence.current || payload.dataset.dataset_id !== datasetId) return;
      setAnalysis(payload); setExploration(undefined);
      if (navigation === navigationSequence.current) setStage("analysis");
    } catch (error) {
      if (!controller.signal.aborted && generation === requestSequence.current && request === analysisSequence.current) setAnalysisError(error instanceof Error ? error.message : "UCI analysis failed. Please try again.");
    } finally { if (generation === requestSequence.current && request === analysisSequence.current) setAnalysisLoading(false); }
  }
  const liveInterpretation = analysisMode === "live" ? discovery?.interpretation ?? null : EXAMPLE_INTERPRETATION;
  const liveDatasets = analysisMode === "live" ? discovery?.datasets ?? [] : EXAMPLE_DATASETS;
  return <div className={`site-shell${stage === "graph" ? " graph-active" : ""}`}>
    <header className="site-header">
      <div className="brand-row"><span className="brand">DataOPedia</span><span className="preview-label">{analysisMode === "live" ? "Live repository search" : "Static preview · cached UCI example"}</span><div className="header-actions"><ThemeToggle />{authControls}</div></div>
      <nav aria-label="Research navigation" className="stage-nav">
        {stages.map(({ key, label }, index) => <button type="button" key={key} aria-current={stage === key ? "page" : undefined} onClick={() => navigate(key)}><span className="nav-index" aria-hidden="true">0{index + 1}</span>{label}</button>)}
      </nav>
    </header>
    <main id="main-content" className="stage-main">{stage !== "question" && stage !== "graph" && stage !== "history" && stage !== "connections" && <div className="example-context"><span className="data-label">{analysisMode === "live" ? "Research question" : "Cached example question"}</span><span>{analysisMode === "live" ? activeQuestion : EXAMPLE_QUESTION}</span><button type="button" onClick={() => navigate("question")}>Revise question</button></div>}{stage === "question" ? <ResearchQuestion exampleQuestion={EXAMPLE_QUESTION} apiBase={apiBase} onOpenResearch={openResearch} onExploreExample={() => { requestSequence.current += 1; searchController.current?.abort(); analysisController.current?.abort(); analysisSequence.current++; setAnalysisLoading(false); graphSession.current = newSession(); setDiscovery(null); setActiveQuestion(EXAMPLE_QUESTION); setAnalysisMode("preview"); setAnalysis(EXAMPLE_ANALYSIS); setExploration(EXAMPLE_EXPLORATION); setAnalysisError(""); setGraph(null); setGraphError(""); setGraphLoading(false); setStage("interpretation"); }} onSearch={liveSearchEnabled ? search : undefined} /> : stage === "history" ? <PastResearch apiBase={apiBase} selectedQueryId={selectedQueryId} onSelectQuery={setSelectedQueryId} onOpenConnections={openConnections} /> : stage === "connections" ? <ResearchConnectionsGraph apiBase={apiBase} onSelectQuery={openResearch} /> : stage === "interpretation" ? <InterpretationSheet interpretation={liveInterpretation} processingMode={analysisMode === "live" ? discovery?.processing_mode : "keyword_fallback"} onSearchQuestion={liveSearchEnabled ? search : undefined} /> : stage === "datasets" ? <DatasetLedger datasets={liveDatasets} discovery={analysisMode === "live" ? discovery : null} analysisMode={analysisMode} analysisLoading={analysisLoading} analysisError={analysisError} onOpenAnalysis={openAnalysis} onOpenGraph={() => navigate("graph")} /> : stage === "graph" ? <Suspense fallback={<p role="status">Loading graph workspace…</p>}><DatasetGraph graph={graph} datasets={liveDatasets} loading={graphLoading} error={graphError} question={activeQuestion} generation={requestSequence.current} cached={analysisMode === "preview"} interpretation={liveInterpretation} keyword={analysisMode === "preview" || discovery?.processing_mode === "keyword_fallback"} analysis={analysis} onAnalyze={openAnalysis} analysisLoading={analysisLoading} analysisError={analysisError} sessionRef={graphSession} onRetry={analysisMode === "live" && discovery ? () => void loadGraph(activeQuestion, requestSequence.current) : undefined} /></Suspense> : analysisMode === "live" && !analysis ? <section className="analysis-page" aria-labelledby="analysis-title"><p className="eyebrow">Research instrument / 05 — Analysis</p><h1 id="analysis-title">Analysis</h1><div className="empty-state" role="status"><h2>No dataset analyzed</h2><p>Select an eligible UCI dataset from the discovery ledger to load a computed profile.</p></div></section> : <AnalysisView analysis={analysis ?? EXAMPLE_ANALYSIS} exploration={analysisMode === "live" ? exploration : EXAMPLE_EXPLORATION} />}</main>
    {stage !== "graph" && <footer className="site-footer">DataOPedia / Research instrument · {analysisMode === "live" ? "Live repository metadata" : "Cached UCI example"}</footer>}
  </div>;
}

export default App;
