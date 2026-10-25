import { useState } from "react";
import { ResearchQuestion } from "./components/ResearchQuestion";
import { EXAMPLE_QUESTION } from "./demo/researchExample";
import { EXAMPLE_INTERPRETATION } from "./demo/researchExample";
import { InterpretationSheet } from "./components/InterpretationSheet";
import { DatasetLedger } from "./components/DatasetLedger";
import { EXAMPLE_DATASETS } from "./demo/researchExample";
import { EXAMPLE_ANALYSIS } from "./demo/researchExample";
import { KnowledgeGraphShell } from "./components/KnowledgeGraphShell";

export type PreviewStage = "question" | "interpretation" | "datasets" | "graph" | "analysis";
const stages: { key: PreviewStage; label: string }[] = [
  { key: "question", label: "Question" }, { key: "interpretation", label: "Interpretation" },
  { key: "datasets", label: "Datasets" }, { key: "graph", label: "Graph" },
  { key: "analysis", label: "Analysis" },
];

function App() {
  const [stage, setStage] = useState<PreviewStage>("question");
  return <div className="site-shell">
    <header className="site-header">
      <div className="brand-row"><span className="brand">DataOPedia</span><span className="preview-label">Static preview · cached UCI example</span></div>
      <nav aria-label="Preview stages" className="stage-nav">
        {stages.map(({ key, label }, index) => <button type="button" key={key} aria-current={stage === key ? "page" : undefined} onClick={() => setStage(key)}><span className="nav-index" aria-hidden="true">0{index + 1}</span>{label}</button>)}
      </nav>
    </header>
    <main id="main-content" className="stage-main">{stage === "question" ? <ResearchQuestion exampleQuestion={EXAMPLE_QUESTION} onExploreExample={() => setStage("interpretation")} /> : stage === "interpretation" ? <><InterpretationSheet interpretation={EXAMPLE_INTERPRETATION} processingMode="keyword_fallback" /><button type="button" className="secondary-action back-action" onClick={() => setStage("question")}>Revise question</button></> : stage === "datasets" ? <DatasetLedger datasets={EXAMPLE_DATASETS} onOpenAnalysis={() => setStage("analysis")} /> : stage === "graph" ? <KnowledgeGraphShell interpretation={EXAMPLE_INTERPRETATION} datasets={EXAMPLE_DATASETS} analysis={EXAMPLE_ANALYSIS} /> : <h1>{stages.find((item) => item.key === stage)?.label}</h1>}</main>
    <footer className="site-footer">DataOPedia / Research instrument · Cached UCI example</footer>
  </div>;
}

export default App;
