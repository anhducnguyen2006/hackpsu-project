import type { ReactNode } from "react";
import { useRef, useState } from "react";
import { ResearchQuestion } from "./components/ResearchQuestion";
import { EXAMPLE_QUESTION } from "./demo/researchExample";
import { EXAMPLE_INTERPRETATION } from "./demo/researchExample";
import { InterpretationSheet } from "./components/InterpretationSheet";
import { DatasetLedger } from "./components/DatasetLedger";
import { EXAMPLE_DATASETS } from "./demo/researchExample";
import { EXAMPLE_ANALYSIS } from "./demo/researchExample";
import { DatasetGraph } from "./components/DatasetGraph";
import { AnalysisView } from "./components/AnalysisView";
import { EXAMPLE_EXPLORATION } from "./demo/researchExample";
import { PastResearch } from "./components/PastResearch";
import type { AuthorizedFetch } from "./auth/api";
import { protectedRequestError } from "./auth/api";
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

function App({ authControls, authorizedFetch }: { authControls?: ReactNode; authorizedFetch?: AuthorizedFetch }) {
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
  const [researchQueryId, setResearchQueryId] = useState<number | null>(null);
  const requestSequence = useRef(0);
  const analysisSequence = useRef(0);
  const searchController = useRef<AbortController | null>(null);
  const analysisController = useRef<AbortController | null>(null);
  const apiBase = getApiBase();
  const liveSearchEnabled = Boolean(apiBase);
  function openResearch(queryId: number) {
    setSelectedQueryId(queryId);
    setStage("history");
  }
  function openConnections() {
    setStage("connections");
  }
  async function search(question: string) {
    if (!apiBase) throw new Error("Live search is not configured for this frontend.");
    if (!authorizedFetch) throw new Error("Log in to search live repositories.");
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    const sequence = ++requestSequence.current;
    setDiscovery(null);
    setResearchQueryId(null);
    setActiveQuestion(question);
    setAnalysisMode("live");
    setAnalysis(null);
    setExploration(undefined);
    setAnalysisError("");
    setGraph(null);
    setGraphError("");
    setGraphLoading(true);
    try {
      const response = await authorizedFetch(`${apiBase}/api/v1/discovery/search`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: question, limit: 12 }), signal: controller.signal });
      if (!response.ok) throw new Error(protectedRequestError(response.status, "The discovery service could not complete this search. Check that the backend is running and try again."));
      const payload = await response.json() as DiscoveryResponse;
      if (sequence !== requestSequence.current) return;
      setDiscovery(payload);
      setResearchQueryId(payload.research_query_id ?? null);
      try {
        const graphResponse = await authorizedFetch(`${apiBase}/api/v1/discovery/graph`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: question, limit: 12 }), signal: controller.signal });
        if (!graphResponse.ok) throw new Error(protectedRequestError(graphResponse.status, "The dataset graph could not be loaded for this search."));
        if (sequence === requestSequence.current) setGraph(await graphResponse.json() as DatasetGraphResponse);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (sequence === requestSequence.current) setGraphError(error instanceof Error ? error.message : "The dataset graph could not be loaded.");
      } finally {
        if (sequence === requestSequence.current) setGraphLoading(false);
      }
      setStage("interpretation");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      throw error;
    }
  }
  async function openAnalysis(datasetId: string, resourceId?: string) {
    if (analysisMode === "preview") { setStage("analysis"); return; }
    if (!apiBase || !authorizedFetch) return;
    analysisController.current?.abort();
    const controller = new AbortController();
    analysisController.current = controller;
    const sequence = ++analysisSequence.current;
    setAnalysis(null);
    setExploration(undefined);
    setAnalysisLoading(true);
    setAnalysisError("");
    try {
      const response = await authorizedFetch(`${apiBase}/api/v1/datasets/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dataset_id: datasetId, research_question: activeQuestion, ...(resourceId ? { resource_id: resourceId } : {}), ...(researchQueryId ? { research_query_id: researchQueryId } : {}) }), signal: controller.signal });
      if (sequence !== analysisSequence.current) return;
      if (!response.ok) throw new Error(protectedRequestError(response.status, "Analysis is unavailable for this dataset right now."));
      const payload = await response.json() as DatasetAnalysisResponse;
      if (sequence !== analysisSequence.current) return;
      if (payload.research_query_id) setResearchQueryId(payload.research_query_id);
      setAnalysis(payload);
      setExploration(undefined);
      setStage("analysis");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (sequence !== analysisSequence.current) return;
      setAnalysisError(error instanceof Error ? error.message : "Analysis failed. Please try again.");
    } finally {
      if (sequence === analysisSequence.current) setAnalysisLoading(false);
    }
  }
  const liveInterpretation = analysisMode === "live" ? discovery?.interpretation ?? null : EXAMPLE_INTERPRETATION;
  const liveDatasets = analysisMode === "live" ? discovery?.datasets ?? [] : EXAMPLE_DATASETS;
  return <div className="site-shell">
    <header className="site-header">
      <div className="brand-row"><span className="brand">DataOPedia</span><span className="preview-label">{analysisMode === "live" ? "Live repository search" : "Static preview · cached UCI example"}</span>{authControls}</div>
      <nav aria-label="Research navigation" className="stage-nav">
        {stages.map(({ key, label }, index) => <button type="button" key={key} aria-current={stage === key ? "page" : undefined} onClick={() => setStage(key)}><span className="nav-index" aria-hidden="true">0{index + 1}</span>{label}</button>)}
      </nav>
    </header>
    <main id="main-content" className="stage-main">{stage !== "question" && stage !== "history" && stage !== "connections" && <div className="example-context"><span className="data-label">{analysisMode === "live" ? "Research question" : "Cached example question"}</span><span>{analysisMode === "live" ? activeQuestion : EXAMPLE_QUESTION}</span><button type="button" onClick={() => setStage("question")}>Revise question</button></div>}{stage === "question" ? <ResearchQuestion exampleQuestion={EXAMPLE_QUESTION} apiBase={apiBase} authorizedFetch={authorizedFetch} onOpenResearch={openResearch} onExploreExample={() => { requestSequence.current += 1; analysisController.current?.abort(); analysisSequence.current += 1; setDiscovery(null); setResearchQueryId(null); setActiveQuestion(EXAMPLE_QUESTION); setAnalysisMode("preview"); setAnalysis(EXAMPLE_ANALYSIS); setExploration(EXAMPLE_EXPLORATION); setAnalysisError(""); setGraph(null); setGraphError(""); setGraphLoading(false); setStage("interpretation"); }} onSearch={liveSearchEnabled ? search : undefined} /> : stage === "history" ? <PastResearch apiBase={apiBase} authorizedFetch={authorizedFetch} selectedQueryId={selectedQueryId} onSelectQuery={setSelectedQueryId} onOpenConnections={openConnections} /> : stage === "connections" ? <ResearchConnectionsGraph apiBase={apiBase} onSelectQuery={openResearch} /> : stage === "interpretation" ? <InterpretationSheet interpretation={liveInterpretation} processingMode={analysisMode === "live" ? discovery?.processing_mode : "keyword_fallback"} onSearchQuestion={liveSearchEnabled ? search : undefined} /> : stage === "datasets" ? <DatasetLedger datasets={liveDatasets} discovery={analysisMode === "live" ? discovery : null} analysisMode={analysisMode} analysisLoading={analysisLoading} analysisError={analysisError} onOpenAnalysis={openAnalysis} graph={graph} graphLoading={graphLoading} graphError={graphError} /> : stage === "graph" ? <DatasetGraph graph={graph} datasets={liveDatasets} loading={graphLoading} error={graphError} /> : analysisMode === "live" && !analysis ? <section className="analysis-page" aria-labelledby="analysis-title"><p className="eyebrow">Research instrument / 05 — Analysis</p><h1 id="analysis-title">Analysis</h1><div className="empty-state" role="status"><h2>No dataset analyzed</h2><p>Select one supported data file from the discovery ledger. The server retrieves that file and computes the profile.</p></div></section> : <AnalysisView analysis={analysis ?? EXAMPLE_ANALYSIS} exploration={analysisMode === "live" ? exploration : EXAMPLE_EXPLORATION} presentation={analysisMode === "live" ? "computed" : "preview"} />}</main>
    <footer className="site-footer">DataOPedia / Research instrument · {analysisMode === "live" ? "Live repository metadata" : "Cached UCI example"}</footer>
  </div>;
}

export default App;
