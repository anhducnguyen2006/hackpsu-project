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
import type { DatasetAnalysisResponse, DatasetGraphResponse, DiscoveryResponse, ExploratoryAnalysisResponse } from "./types";

export type PreviewStage = "question" | "interpretation" | "datasets" | "graph" | "analysis";
const stages: { key: PreviewStage; label: string }[] = [
  { key: "question", label: "Question" }, { key: "interpretation", label: "Interpretation" },
  { key: "datasets", label: "Datasets" }, { key: "graph", label: "Graph" },
  { key: "analysis", label: "Analysis" },
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
  const requestSequence = useRef(0);
  const searchController = useRef<AbortController | null>(null);
  const apiBase = getApiBase();
  const liveSearchEnabled = Boolean(apiBase);
  async function search(question: string) {
    if (!apiBase) throw new Error("Live search is not configured for this frontend.");
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    const sequence = ++requestSequence.current;
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
      try {
        const graphResponse = await fetch(`${apiBase}/api/v1/discovery/graph`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: question, limit: 12 }), signal: controller.signal });
        if (!graphResponse.ok) throw new Error("The dataset graph could not be loaded for this search.");
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
  async function openAnalysis(datasetId: string) {
    if (analysisMode === "preview") { setStage("analysis"); return; }
    if (!datasetId.startsWith("uci:")) return;
    if (!apiBase) return;
    setAnalysisLoading(true);
    setAnalysisError("");
    try {
      const response = await fetch(`${apiBase}/api/v1/datasets/${encodeURIComponent(datasetId)}/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: activeQuestion }) });
      if (!response.ok) throw new Error("UCI analysis is unavailable for this dataset right now.");
      setAnalysis(await response.json() as DatasetAnalysisResponse);
      setExploration(undefined);
      setStage("analysis");
    } catch (error) {
      setAnalysisError(error instanceof Error ? error.message : "UCI analysis failed. Please try again.");
    } finally {
      setAnalysisLoading(false);
    }
  }
  const liveInterpretation = analysisMode === "live" ? discovery?.interpretation ?? null : EXAMPLE_INTERPRETATION;
  const liveDatasets = analysisMode === "live" ? discovery?.datasets ?? [] : EXAMPLE_DATASETS;
  return <div className="site-shell">
    <header className="site-header">
      <div className="brand-row"><span className="brand">DataOPedia</span><span className="preview-label">{analysisMode === "live" ? "Live repository search" : "Static preview · cached UCI example"}</span>{authControls}</div>
      <nav aria-label="Preview stages" className="stage-nav">
        {stages.map(({ key, label }, index) => <button type="button" key={key} aria-current={stage === key ? "page" : undefined} onClick={() => setStage(key)}><span className="nav-index" aria-hidden="true">0{index + 1}</span>{label}</button>)}
      </nav>
    </header>
    <main id="main-content" className="stage-main">{stage !== "question" && <div className="example-context"><span className="data-label">{analysisMode === "live" ? "Research question" : "Cached example question"}</span><span>{analysisMode === "live" ? activeQuestion : EXAMPLE_QUESTION}</span><button type="button" onClick={() => setStage("question")}>Revise question</button></div>}{stage === "question" ? <ResearchQuestion exampleQuestion={EXAMPLE_QUESTION} onExploreExample={() => { requestSequence.current += 1; setDiscovery(null); setActiveQuestion(EXAMPLE_QUESTION); setAnalysisMode("preview"); setAnalysis(EXAMPLE_ANALYSIS); setExploration(EXAMPLE_EXPLORATION); setAnalysisError(""); setGraph(null); setGraphError(""); setGraphLoading(false); setStage("interpretation"); }} onSearch={liveSearchEnabled ? search : undefined} /> : stage === "interpretation" ? <InterpretationSheet interpretation={liveInterpretation} processingMode={analysisMode === "live" ? discovery?.processing_mode : "keyword_fallback"} onSearchQuestion={liveSearchEnabled ? search : undefined} /> : stage === "datasets" ? <DatasetLedger datasets={liveDatasets} discovery={analysisMode === "live" ? discovery : null} analysisMode={analysisMode} analysisLoading={analysisLoading} analysisError={analysisError} onOpenAnalysis={openAnalysis} graph={graph} graphLoading={graphLoading} graphError={graphError} /> : stage === "graph" ? <DatasetGraph graph={graph} datasets={liveDatasets} loading={graphLoading} error={graphError} /> : analysisMode === "live" && !analysis ? <section className="analysis-page" aria-labelledby="analysis-title"><p className="eyebrow">Research instrument / 05 — Analysis</p><h1 id="analysis-title">Analysis</h1><div className="empty-state" role="status"><h2>No dataset analyzed</h2><p>Select an eligible UCI dataset from the discovery ledger to load a computed profile.</p></div></section> : <AnalysisView analysis={analysis ?? EXAMPLE_ANALYSIS} exploration={analysisMode === "live" ? exploration : EXAMPLE_EXPLORATION} />}</main>
    <footer className="site-footer">DataOPedia / Research instrument · {analysisMode === "live" ? "Live repository metadata" : "Cached UCI example"}</footer>
  </div>;
}

export default App;
