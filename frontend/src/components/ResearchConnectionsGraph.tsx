import { useCallback, useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type { ResearchGraphEdgeData, ResearchGraphNodeData, ResearchGraphResponse } from "../types";

type ResearchConnectionsGraphProps = {
  apiBase?: string;
  onSelectQuery: (queryId: number) => void;
};

function relationshipLabel(type: ResearchGraphEdgeData["relationship_type"]) {
  return type === "SHARED_DATASET" ? "Shared dataset" : "Semantic similarity";
}

function scoreLabel(score: number | null) {
  return score === null ? "Score unavailable" : score.toFixed(3);
}

function shortenQuestion(question: string, length = 42) {
  return question.length > length ? `${question.slice(0, length - 1).trimEnd()}…` : question;
}

export function ResearchConnectionsGraph({ apiBase, onSelectQuery }: ResearchConnectionsGraphProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const requestControllerRef = useRef<AbortController | null>(null);
  const [graph, setGraph] = useState<ResearchGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedNode, setSelectedNode] = useState<ResearchGraphNodeData | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<ResearchGraphEdgeData | null>(null);
  const [viewMode, setViewMode] = useState<"list" | "canvas">(() => {
    if (typeof window === "undefined") return "canvas";
    return typeof window.matchMedia === "function" && window.matchMedia("(max-width: 640px)").matches ? "list" : "canvas";
  });

  const loadGraph = useCallback(async () => {
    if (!apiBase) {
      setLoading(false);
      setError("Research connections are unavailable until the backend is connected.");
      return;
    }
    requestControllerRef.current?.abort();
    const controller = new AbortController();
    requestControllerRef.current = controller;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/v1/research/graph?limit=100`, { signal: controller.signal });
      if (!response.ok) throw new Error(response.status === 404 ? "The saved research graph is not available yet." : "The saved research graph could not be loaded.");
      const payload = await response.json() as ResearchGraphResponse;
      if (requestControllerRef.current !== controller) return;
      setGraph(payload);
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      if (requestControllerRef.current !== controller) return;
      setError(cause instanceof Error ? cause.message : "The saved research graph could not be loaded.");
    } finally {
      if (requestControllerRef.current === controller) {
        requestControllerRef.current = null;
        setLoading(false);
      }
    }
  }, [apiBase]);

  useEffect(() => {
    void loadGraph();
    return () => {
      requestControllerRef.current?.abort();
      requestControllerRef.current = null;
    };
  }, [loadGraph]);

  useEffect(() => {
    if (!containerRef.current || loading || error || !graph || graph.nodes.length === 0) return;
    cyRef.current?.destroy();
    const cy = cytoscape({
      container: containerRef.current,
      elements: [...graph.nodes.map(({ data }) => ({ data: { ...data, display_label: `${data.research_id}\n${shortenQuestion(data.question, 28)}` } })), ...graph.edges.map(({ data }) => ({ data }))],
      layout: { name: "cose", animate: false, padding: 44, fit: true },
      style: [
        { selector: "node", style: { label: "data(display_label)", color: "#3A0F34", "font-family": "Georgia, serif", "font-size": 12, "text-wrap": "wrap", "text-max-width": "88px", "text-overflow-wrap": "anywhere", "text-valign": "center", "text-halign": "center", width: 116, height: 76, shape: "round-rectangle", "background-color": "#F6F7F6", "border-width": 2, "border-color": "#3A0F34", "overlay-opacity": 0 } },
        { selector: "edge", style: { width: 2, "line-color": "#8D7888", "curve-style": "bezier", "target-arrow-shape": "none", opacity: 0.82 } },
        { selector: 'edge[relationship_type = "SEMANTIC_SIMILARITY"]', style: { "line-style": "dashed", "line-color": "#8D7888" } },
        { selector: 'edge[relationship_type = "SHARED_DATASET"]', style: { "line-color": "#EAAA00", width: 3 } },
        { selector: ".is-selected", style: { "border-color": "#EAAA00", "border-width": 4, opacity: 1 } },
        { selector: "edge.is-selected", style: { width: 5, opacity: 1 } },
      ],
    });
    cy.on("tap", "node", (event) => {
      const node = event.target.data() as ResearchGraphNodeData;
      setSelectedNode(node);
      setSelectedEdge(null);
      cy.elements().removeClass("is-selected");
      event.target.addClass("is-selected");
      onSelectQuery(node.research_id);
    });
    cy.on("tap", "edge", (event) => {
      setSelectedEdge(event.target.data() as ResearchGraphEdgeData);
      setSelectedNode(null);
      cy.elements().removeClass("is-selected");
      event.target.addClass("is-selected");
    });
    cy.on("tap", (event) => {
      if (event.target === cy) {
        setSelectedNode(null);
        setSelectedEdge(null);
        cy.elements().removeClass("is-selected");
      }
    });
    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, [error, graph, loading, onSelectQuery]);

  useEffect(() => {
    if (viewMode !== "canvas" || !cyRef.current) return;
    cyRef.current.resize();
    cyRef.current.fit(undefined, 44);
  }, [viewMode]);

  function selectNode(node: ResearchGraphNodeData) {
    setSelectedNode(node);
    setSelectedEdge(null);
    cyRef.current?.elements().removeClass("is-selected");
    cyRef.current?.$id(node.id).addClass("is-selected");
    onSelectQuery(node.research_id);
  }

  function selectEdge(edge: ResearchGraphEdgeData) {
    setSelectedEdge(edge);
    setSelectedNode(null);
    cyRef.current?.elements().removeClass("is-selected");
    cyRef.current?.$id(edge.id).addClass("is-selected");
  }

  function fitGraph() {
    cyRef.current?.fit(undefined, 44);
  }

  function resetGraph() {
    setSelectedNode(null);
    setSelectedEdge(null);
    cyRef.current?.elements().removeClass("is-selected");
    fitGraph();
  }

  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];
  const selectedSource = selectedEdge ? nodes.find(({ data }) => data.id === selectedEdge.source)?.data : null;
  const selectedTarget = selectedEdge ? nodes.find(({ data }) => data.id === selectedEdge.target)?.data : null;

  return <section className="research-connections" aria-labelledby="research-connections-title">
    <div className="connections-heading">
      <div><p className="eyebrow">Research instrument / archive map</p><h1 id="research-connections-title">Research Connections</h1><p className="section-deck">Trace how saved questions meet through semantic similarity or an identical discovered dataset.</p></div>
      <span className="evidence-tag">Persisted connections</span>
    </div>
    {loading ? <div className="graph-empty" role="status"><h2>Loading connections</h2><p>Fetching the saved research graph.</p></div> : error ? <div className="graph-empty graph-error" role="alert"><h2>Graph unavailable</h2><p>{error}</p><button type="button" className="secondary-action graph-retry" onClick={() => void loadGraph()}>Retry</button></div> : nodes.length === 0 ? <div className="graph-empty" role="status"><h2>No connected research yet</h2><p>Saved questions will appear here after a semantic or shared-dataset relationship is persisted.</p></div> : <>
      <div className="connections-toolbar"><span className="data-label">{nodes.length} questions / {edges.length} connections</span><div className="graph-actions"><div className="connection-view-toggle" role="group" aria-label="Research graph view"><button type="button" className={viewMode === "list" ? "view-toggle-active" : ""} aria-pressed={viewMode === "list"} onClick={() => setViewMode("list")}>List</button><button type="button" className={viewMode === "canvas" ? "view-toggle-active" : ""} aria-pressed={viewMode === "canvas"} onClick={() => setViewMode("canvas")}>Canvas</button></div><button type="button" className="secondary-action" onClick={fitGraph}>Fit graph</button><button type="button" className="secondary-action" onClick={resetGraph}>Reset selection</button></div></div>
      <div className={`research-graph-layout research-view-${viewMode}`}><div className="research-graph-stage"><div className="research-canvas-panel"><div ref={containerRef} className="research-cytoscape-canvas" role="img" aria-label="Interactive research connections graph" tabIndex={0} /><div className="research-graph-legend" aria-label="Relationship legend"><span><i className="connection-key semantic" />Semantic similarity</span><span><i className="connection-key shared" />Shared dataset</span></div></div><div className="research-node-index" aria-label="Saved research questions"><span className="data-label">Saved questions</span>{nodes.map(({ data }) => <button type="button" key={data.id} className="research-node-button" aria-label={`Open saved research ${data.research_id}: ${data.question}`} aria-pressed={selectedNode?.id === data.id} onClick={() => selectNode(data)}>{data.research_id}. {data.question}</button>)}</div><div className="research-connection-index" aria-label="Saved research connections"><span className="data-label">Connection index</span>{edges.map(({ data }) => { const source = nodes.find(({ data: node }) => node.id === data.source)?.data; const target = nodes.find(({ data: node }) => node.id === data.target)?.data; const descriptor = `${relationshipLabel(data.relationship_type)} · ${shortenQuestion(source?.question ?? data.source)} ↔ ${shortenQuestion(target?.question ?? data.target)} · ${data.shared_dataset_count > 0 ? `${data.shared_dataset_count} dataset${data.shared_dataset_count === 1 ? "" : "s"}` : scoreLabel(data.similarity_score)}`; return <button type="button" key={data.id} className="research-connection-button" aria-label={`${relationshipLabel(data.relationship_type)} between ${source?.question ?? data.source} and ${target?.question ?? data.target}`} aria-pressed={selectedEdge?.id === data.id} onClick={() => selectEdge(data)}>{descriptor}</button>; })}</div></div><aside className="research-graph-detail" aria-live="polite">{selectedNode ? <><span className="data-label">Saved question / {selectedNode.research_id}</span><h2>{selectedNode.question}</h2><p>Open the saved session to inspect its preserved datasets and assessments.</p><button type="button" className="primary-action" onClick={() => onSelectQuery(selectedNode.research_id)}>Open saved research <span aria-hidden="true">↗</span></button></> : selectedEdge ? <><span className="data-label">Connection inspector</span><h2>{relationshipLabel(selectedEdge.relationship_type)}</h2><p className="connection-between">{selectedSource?.question ?? "Research question"} <span aria-hidden="true">↔</span> {selectedTarget?.question ?? "Research question"}</p><dl className="graph-detail-list"><div><dt>Relationship</dt><dd>{selectedEdge.relationship_type.replace(/_/g, " ")}</dd></div>{selectedEdge.relationship_type === "SEMANTIC_SIMILARITY" && <div><dt>Similarity score</dt><dd>{scoreLabel(selectedEdge.similarity_score)}</dd></div>}{selectedEdge.relationship_type === "SHARED_DATASET" && <div><dt>Shared datasets</dt><dd>{selectedEdge.shared_dataset_count}</dd></div>}</dl>{selectedEdge.relationship_type === "SHARED_DATASET" && <div className="shared-dataset-evidence"><span className="data-label">Verified dataset evidence</span>{selectedEdge.shared_datasets.length > 0 ? <ul>{selectedEdge.shared_datasets.map((dataset) => <li key={dataset.dataset_id}><strong>{dataset.title}</strong><span>{dataset.repository} / {dataset.external_id}</span></li>)}</ul> : <p className="muted">Dataset details are unavailable in this graph response.</p>}</div>}<p className="connection-evidence">{selectedEdge.evidence}</p></> : <><span className="data-label">Graph inspector</span><h2>Select a question or connection</h2><p>Questions open their saved session. Connections explain whether the link is semantic or supported by shared discovered datasets.</p></>}</aside></div>
    </>}
  </section>;
}
