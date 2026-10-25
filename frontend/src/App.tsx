import { useState } from "react";
import { ResearchQuestion } from "./components/ResearchQuestion";
import { EXAMPLE_QUESTION } from "./demo/researchExample";
import { EXAMPLE_INTERPRETATION } from "./demo/researchExample";
import { InterpretationSheet } from "./components/InterpretationSheet";
import { DatasetLedger } from "./components/DatasetLedger";
import { EXAMPLE_DATASETS } from "./demo/researchExample";
import { EXAMPLE_ANALYSIS } from "./demo/researchExample";
import { KnowledgeGraphShell } from "./components/KnowledgeGraphShell";
import { AnalysisView } from "./components/AnalysisView";
import { EXAMPLE_EXPLORATION } from "./demo/researchExample";
import type { DatasetAnalysisResponse, DiscoveryResponse, ExploratoryAnalysisResponse } from "./types";

export type PreviewStage = "question" | "interpretation" | "datasets" | "graph" | "analysis";
const stages: { key: PreviewStage; label: string }[] = [
  { key: "question", label: "Question" }, { key: "interpretation", label: "Interpretation" },
  { key: "datasets", label: "Datasets" }, { key: "graph", label: "Graph" },
  { key: "analysis", label: "Analysis" },
];

function App() {
  const [stage, setStage] = useState<PreviewStage>("question");
  const [discovery, setDiscovery] = useState<DiscoveryResponse | null>(null);
  const [activeQuestion, setActiveQuestion] = useState(EXAMPLE_QUESTION);
  const [analysis, setAnalysis] = useState<DatasetAnalysisResponse>(EXAMPLE_ANALYSIS);
  const [exploration, setExploration] = useState<ExploratoryAnalysisResponse | undefined>(EXAMPLE_EXPLORATION);
  const [analysisMode, setAnalysisMode] = useState<"preview" | "live">("preview");
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.MODE === "test" ? undefined : "http://localhost:8000");
  const liveSearchEnabled = Boolean(apiBase);
  async function search(question: string) {
    if (!apiBase) throw new Error("Live search is not configured for this frontend.");
    const response = await fetch(`${apiBase}/api/v1/discovery/search`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: question, limit: 12 }) });
    if (!response.ok) throw new Error("The discovery service could not complete this search.");
    const payload = await response.json() as DiscoveryResponse;
    setDiscovery(payload); setActiveQuestion(question); setAnalysisMode("live"); setStage("datasets");
  }
  async function openAnalysis(datasetId: string) {
    if (analysisMode === "preview") { setStage("analysis"); return; }
    if (!datasetId.startsWith("uci:")) return;
    const response = await fetch(`${apiBase}/api/v1/datasets/${encodeURIComponent(datasetId)}/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ research_question: activeQuestion }) });
    if (!response.ok) throw new Error("UCI analysis is unavailable for this dataset right now.");
    setAnalysis(await response.json() as DatasetAnalysisResponse); setExploration(undefined); setStage("analysis");
  }
  return <div className="site-shell">
    <header className="site-header">
      <div className="brand-row"><span className="brand">DataOPedia</span><span className="preview-label">{discovery ? "Live repository search" : "Static preview · cached UCI example"}</span></div>
      <nav aria-label="Preview stages" className="stage-nav">
        {stages.map(({ key, label }, index) => <button type="button" key={key} aria-current={stage === key ? "page" : undefined} onClick={() => setStage(key)}><span className="nav-index" aria-hidden="true">0{index + 1}</span>{label}</button>)}
      </nav>
    </header>
    <main id="main-content" className="stage-main">{stage !== "question" && <div className="example-context"><span className="data-label">{discovery ? "Research question" : "Cached example question"}</span><span>{discovery ? activeQuestion : EXAMPLE_QUESTION}</span><button type="button" onClick={() => setStage("question")}>Revise question</button></div>}{stage === "question" ? <ResearchQuestion exampleQuestion={EXAMPLE_QUESTION} onExploreExample={() => setStage("interpretation")} onSearch={liveSearchEnabled ? search : undefined} /> : stage === "interpretation" ? <InterpretationSheet interpretation={EXAMPLE_INTERPRETATION} processingMode="keyword_fallback" /> : stage === "datasets" ? <DatasetLedger datasets={discovery?.datasets ?? EXAMPLE_DATASETS} discovery={discovery} analysisMode={analysisMode} onOpenAnalysis={openAnalysis} /> : stage === "graph" ? <KnowledgeGraphShell interpretation={EXAMPLE_INTERPRETATION} datasets={EXAMPLE_DATASETS} analysis={EXAMPLE_ANALYSIS} /> : <AnalysisView analysis={analysisMode === "live" ? analysis : EXAMPLE_ANALYSIS} exploration={analysisMode === "live" ? exploration : EXAMPLE_EXPLORATION} />}</main>
    <footer className="site-footer">DataOPedia / Research instrument · Cached UCI example</footer>
  </div>;
}

export default App;
