import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type { ResearchGraphEdgeData, ResearchGraphNodeData, ResearchGraphResponse } from "../types";
import { observeThemeColors } from "../theme/theme";

type ResearchConnectionsGraphProps = { apiBase?: string; onSelectQuery: (queryId: number) => void };

function relationshipLabel(type: ResearchGraphEdgeData["relationship_type"]) { return type === "SHARED_DATASET" ? "Shared dataset" : "Semantic similarity"; }
function scoreLabel(score: number | null) { return score === null ? "Score unavailable" : score.toFixed(3); }
function shortenQuestion(question: string, length = 42) { return question.length > length ? `${question.slice(0, length - 1).trimEnd()}…` : question; }

function connectionStyles(): cytoscape.StylesheetJson {
  return [
    { selector: "node", style: { label: "data(node_label)", color: "#201c24", "font-family": "Geist, Arial, sans-serif", "font-size": 9, "font-weight": 600, "text-wrap": "wrap", "text-max-width": "76px", "text-overflow-wrap": "anywhere", "text-valign": "center", "text-halign": "center", width: 54, height: 54, shape: "ellipse", "background-color": "#82699c", "border-width": 2, "border-color": "#f6f7f6", "overlay-opacity": 0, "text-outline-width": 0 } },
    { selector: "node.is-selected", style: { "background-color": "#eaaa00", "border-color": "#3a0f34", "border-width": 3, width: 62, height: 62, "font-weight": 700 } },
    { selector: "node.is-hovered", style: { "border-color": "#287f8c", "border-width": 3, width: 62, height: 62 } },
    { selector: "edge", style: { width: 1, "line-color": "#7f7888", "curve-style": "bezier", "target-arrow-shape": "none", opacity: 0.34 } },
    { selector: 'edge[relationship_type = "SEMANTIC_SIMILARITY"]', style: { "line-style": "dashed", "line-color": "#82699c" } },
    { selector: 'edge[relationship_type = "SHARED_DATASET"]', style: { "line-color": "#287f8c", width: 1.5 } },
    { selector: "edge.is-selected", style: { width: 3, opacity: 1, "line-color": "#eaaa00" } },
    { selector: "edge.is-hovered", style: { width: 2.5, opacity: 0.9 } },
  ];
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
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [showSemantic, setShowSemantic] = useState(true);
  const [showShared, setShowShared] = useState(true);
  const [minimumSimilarity, setMinimumSimilarity] = useState("0");
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "canvas">(() => {
    if (typeof window === "undefined") return "canvas";
    const media = typeof window.matchMedia === "function" ? window.matchMedia("(max-width: 640px)") : null;
    return media?.matches && media.media === "(max-width: 640px)" ? "list" : "canvas";
  });

  const loadGraph = useCallback(async () => {
    if (!apiBase) { setLoading(false); setError("Research connections are unavailable until the backend is connected."); return; }
    requestControllerRef.current?.abort();
    const controller = new AbortController(); requestControllerRef.current = controller; setLoading(true); setError("");
    try {
      const response = await fetch(`${apiBase}/api/v1/research/graph?limit=100`, { signal: controller.signal });
      if (!response.ok) throw new Error(response.status === 404 ? "The saved research graph is not available yet." : "The saved research graph could not be loaded.");
      const payload = await response.json() as ResearchGraphResponse;
      if (requestControllerRef.current !== controller) return;
      setGraph(payload);
      setInspectorOpen(payload.nodes.length < 8);
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      if (requestControllerRef.current !== controller) return;
      setError(cause instanceof Error ? cause.message : "The saved research graph could not be loaded.");
    } finally {
      if (requestControllerRef.current === controller) { requestControllerRef.current = null; setLoading(false); }
    }
  }, [apiBase]);

  useEffect(() => { void loadGraph(); return () => { requestControllerRef.current?.abort(); requestControllerRef.current = null; }; }, [loadGraph]);

  const nodes = graph?.nodes.map(({ data }) => data) ?? [];
  const edges = graph?.edges.map(({ data }) => data) ?? [];
  const visible = useMemo(() => {
    const threshold = Number(minimumSimilarity) || 0; const query = search.trim().toLowerCase();
    const filteredNodes = nodes.filter(node => !query || node.question.toLowerCase().includes(query) || String(node.research_id).includes(query));
    const ids = new Set(filteredNodes.map(node => node.id));
    const filteredEdges = edges.filter(edge => {
      if (!ids.has(edge.source) || !ids.has(edge.target)) return false;
      if (edge.relationship_type === "SEMANTIC_SIMILARITY") return showSemantic && (edge.similarity_score === null || edge.similarity_score >= threshold);
      return showShared;
    });
    const connected = new Set(filteredEdges.flatMap(edge => [edge.source, edge.target]));
    return { nodes: filteredNodes.filter(node => filteredEdges.length === 0 || connected.has(node.id)), edges: filteredEdges };
  }, [edges, minimumSimilarity, nodes, search, showSemantic, showShared]);

  useEffect(() => {
    if (!containerRef.current || loading || error || !graph || graph.nodes.length === 0 || viewMode !== "canvas") return;
    cyRef.current?.destroy();
    const cy = cytoscape({
      container: containerRef.current,
      elements: [...visible.nodes.map(data => ({ data: { ...data, node_label: shortenQuestion(data.question, 22), display_label: `${data.research_id}\n${shortenQuestion(data.question, 28)}` } })), ...visible.edges.map(data => ({ data }))],
      layout: { name: "cose", animate: false, fit: true, padding: 64, idealEdgeLength: 150, nodeRepulsion: 900000, nestingFactor: 0.9, gravity: 0.35, numIter: 1000 },
      style: connectionStyles(), minZoom: 0.2, maxZoom: 3,
    });
    cy.on("tap", "node", event => { const node = event.target.data() as ResearchGraphNodeData; setSelectedNode(node); setSelectedEdge(null); setInspectorOpen(true); cy.elements().removeClass("is-selected"); event.target.addClass("is-selected"); onSelectQuery(node.research_id); });
    cy.on("tap", "edge", event => { setSelectedEdge(event.target.data() as ResearchGraphEdgeData); setSelectedNode(null); setInspectorOpen(true); cy.elements().removeClass("is-selected"); event.target.addClass("is-selected"); });
    cy.on("mouseover", "node", event => event.target.addClass("is-hovered")); cy.on("mouseout", "node", event => event.target.removeClass("is-hovered"));
    cy.on("mouseover", "edge", event => event.target.addClass("is-hovered")); cy.on("mouseout", "edge", event => event.target.removeClass("is-hovered"));
    cy.on("tap", event => { if (event.target === cy) { setSelectedNode(null); setSelectedEdge(null); cy.elements().removeClass("is-selected"); } });
    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, [error, graph, loading, onSelectQuery, viewMode, visible]);

  useEffect(() => observeThemeColors(() => { cyRef.current?.style(connectionStyles()).update(); }), []);

  useEffect(() => { if (viewMode === "canvas" && cyRef.current) { cyRef.current.resize(); cyRef.current.fit(undefined, 64); } }, [viewMode]);
  function selectNode(node: ResearchGraphNodeData) { setSelectedNode(node); setSelectedEdge(null); setInspectorOpen(true); cyRef.current?.elements().removeClass("is-selected"); cyRef.current?.$id(node.id).addClass("is-selected"); onSelectQuery(node.research_id); }
  function selectEdge(edge: ResearchGraphEdgeData) { setSelectedEdge(edge); setSelectedNode(null); setInspectorOpen(true); cyRef.current?.elements().removeClass("is-selected"); cyRef.current?.$id(edge.id).addClass("is-selected"); }
  function fitGraph() { cyRef.current?.fit(undefined, 64); }
  function zoomGraph(factor: number) { const cy = cyRef.current; if (cy) cy.zoom({ level: Math.min(3, Math.max(0.2, cy.zoom() * factor)), renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }); }
  function resetGraph() { setSelectedNode(null); setSelectedEdge(null); cyRef.current?.elements().removeClass("is-selected"); fitGraph(); }

  const selectedSource = selectedEdge ? nodes.find(node => node.id === selectedEdge.source) : null;
  const selectedTarget = selectedEdge ? nodes.find(node => node.id === selectedEdge.target) : null;
  const relatedNodes = selectedNode ? edges.filter(edge => edge.source === selectedNode.id || edge.target === selectedNode.id).map(edge => ({ edge, node: nodes.find(node => node.id === (edge.source === selectedNode.id ? edge.target : edge.source)) })).filter(item => item.node) : [];

  return <section className={`research-connections research-graph-workspace research-view-${viewMode}`} aria-labelledby="research-connections-title">
    <div className="research-graph-heading"><p className="eyebrow">Research instrument / archive map</p><h1 id="research-connections-title">Research Connections</h1><p className="section-deck">Explore relationships between your past research questions.</p><span className="research-graph-count">{nodes.length} saved questions · {edges.length} persisted connections</span></div>
    {loading ? <div className="graph-empty" role="status"><h2>Loading connections</h2><p>Fetching the saved research graph.</p></div> : error ? <div className="graph-empty graph-error" role="alert"><h2>Graph unavailable</h2><p>{error}</p><button type="button" className="secondary-action graph-retry" onClick={() => void loadGraph()}>Retry</button></div> : nodes.length === 0 ? <div className="graph-empty" role="status"><h2>No connected research yet</h2><p>Saved questions will appear here after a semantic or shared-dataset relationship is persisted.</p></div> : <>
      <div ref={containerRef} className={`research-cytoscape-canvas ${viewMode === "list" ? "is-list-view" : ""}`} role="img" aria-label="Interactive research connections graph" tabIndex={0} />
      <details className="graph-filters research-filters" open={filtersOpen} onToggle={event => setFiltersOpen(event.currentTarget.open)}><summary>Filters <span className="graph-filter-active">{[!showSemantic, !showShared, Number(minimumSimilarity) > 0, Boolean(search)].filter(Boolean).length || ""}</span></summary><div className="graph-filter-body"><fieldset><legend>Connection type</legend><label><input type="checkbox" checked={showSemantic} onChange={event => setShowSemantic(event.target.checked)} />Semantic similarity <span className="graph-filter-count">{edges.filter(edge => edge.relationship_type === "SEMANTIC_SIMILARITY").length}</span></label><label><input type="checkbox" checked={showShared} onChange={event => setShowShared(event.target.checked)} />Shared dataset <span className="graph-filter-count">{edges.filter(edge => edge.relationship_type === "SHARED_DATASET").length}</span></label></fieldset><label className="research-filter-label">Minimum semantic similarity<input type="number" min="0" max="1" step="0.01" value={minimumSimilarity} onChange={event => setMinimumSimilarity(event.target.value)} /></label><label className="research-filter-label">Search saved questions<input type="search" placeholder="Find a question" value={search} onChange={event => setSearch(event.target.value)} /></label><button type="button" onClick={() => { setShowSemantic(true); setShowShared(true); setMinimumSimilarity("0"); setSearch(""); }}>Reset filters</button></div></details>
      <div className="research-graph-toolbar graph-tools" aria-label="Graph actions"><button type="button" aria-label="Zoom in" title="Zoom in" onClick={() => zoomGraph(1.2)}>+</button><button type="button" aria-label="Zoom out" title="Zoom out" onClick={() => zoomGraph(0.84)}>−</button><button type="button" aria-label="Fit graph" title="Fit graph" onClick={fitGraph}>⌗</button><button type="button" aria-label="Reset selection" title="Reset selection" onClick={resetGraph}>↺</button><span className="research-view-toggle" role="group" aria-label="Research graph view"><button type="button" aria-pressed={viewMode === "list"} className="research-list-toggle" onClick={() => setViewMode("list")}>List</button><button type="button" aria-pressed={viewMode === "canvas"} className="research-list-toggle" onClick={() => setViewMode("canvas")}>Canvas</button></span></div>
      <aside className={`research-graph-detail research-inspector${inspectorOpen ? "" : " is-collapsed"}`} aria-live="polite"><button type="button" className="research-inspector-toggle" aria-label={inspectorOpen ? "Collapse inspector" : "Expand inspector"} onClick={() => setInspectorOpen(open => !open)}>{inspectorOpen ? "×" : "Inspect"}</button>{inspectorOpen && <div className="research-inspector-content">{selectedNode ? <><span className="data-label">Saved question / {selectedNode.research_id}</span><h2>{selectedNode.question}</h2><dl className="graph-detail-list"><div><dt>Research session ID</dt><dd>{selectedNode.research_id}</dd></div><div><dt>Saved</dt><dd>{new Date(selectedNode.created_at).toLocaleDateString()}</dd></div></dl><button type="button" className="primary-action" onClick={() => onSelectQuery(selectedNode.research_id)}>Open saved research <span aria-hidden="true">↗</span></button><div className="research-related"><span className="data-label">Related research questions</span>{relatedNodes.length ? <ul>{relatedNodes.map(({ edge, node }) => <li key={edge.id}><button type="button" onClick={() => selectNode(node!)}>{node!.question}<small>{relationshipLabel(edge.relationship_type)}{edge.similarity_score !== null ? ` · ${scoreLabel(edge.similarity_score)}` : ""}</small></button></li>)}</ul> : <p className="muted">No visible persisted connections.</p>}</div></> : selectedEdge ? <><span className="data-label">Connection inspector</span><h2>{relationshipLabel(selectedEdge.relationship_type)}</h2><p className="connection-between">{selectedSource?.question ?? selectedEdge.source} <span aria-hidden="true">↔</span> {selectedTarget?.question ?? selectedEdge.target}</p><dl className="graph-detail-list"><div><dt>Connection type</dt><dd>{selectedEdge.relationship_type.replace(/_/g, " ")}</dd></div>{selectedEdge.similarity_score !== null && <div><dt>Similarity score</dt><dd>{scoreLabel(selectedEdge.similarity_score)}</dd></div>}{selectedEdge.relationship_type === "SHARED_DATASET" && <div><dt>Shared datasets</dt><dd>{selectedEdge.shared_dataset_count}</dd></div>}</dl>{selectedEdge.relationship_type === "SHARED_DATASET" && <div className="shared-dataset-evidence"><span className="data-label">Verified dataset evidence</span>{selectedEdge.shared_datasets.length > 0 ? <ul>{selectedEdge.shared_datasets.map(dataset => <li key={dataset.dataset_id}><strong>{dataset.title}</strong><span>{dataset.repository} / {dataset.external_id}</span></li>)}</ul> : <p className="muted">Dataset details are unavailable in this graph response.</p>}</div>}<p className="connection-evidence">{selectedEdge.evidence}</p></> : <><span className="data-label">Graph inspector</span><h2>Select a question or connection</h2><p>Questions open their saved session. Connections explain whether the link is semantic or supported by shared discovered datasets.</p></>}{!selectedNode && !selectedEdge && <details className="research-directory" open><summary>Saved questions ({nodes.length})</summary><ul>{nodes.map(node => <li key={node.id}><button type="button" aria-label={`Open saved research ${node.research_id}: ${node.question}`} onClick={() => selectNode(node)}>{node.research_id}. {shortenQuestion(node.question, 80)}</button></li>)}</ul></details>}<div className="research-connection-index-compat"><span className="data-label">Connections ({edges.length})</span><ul>{edges.map(edge => { const source = nodes.find(node => node.id === edge.source); const target = nodes.find(node => node.id === edge.target); const name = `${relationshipLabel(edge.relationship_type)} between ${source?.question ?? edge.source} and ${target?.question ?? edge.target}`; return <li key={edge.id}><button type="button" aria-label={name} aria-pressed={selectedEdge?.id === edge.id} onClick={() => selectEdge(edge)}>{relationshipLabel(edge.relationship_type)} · {shortenQuestion(source?.question ?? edge.source)} ↔ {shortenQuestion(target?.question ?? edge.target)}</button></li>; })}</ul></div></div>}</aside>
      {viewMode === "list" && <div className="research-list-surface" role="dialog" aria-label="Browse saved research connections"><div className="research-list-header"><span className="data-label">Research graph index</span><button type="button" onClick={() => setViewMode("canvas")}>Close</button></div><h2>Saved questions</h2><ul>{visible.nodes.map(node => <li key={node.id}><button type="button" onClick={() => { selectNode(node); setViewMode("canvas"); }}>{node.research_id}. {node.question}</button></li>)}</ul><h2>Connections</h2><ul>{visible.edges.map(edge => { const source = nodes.find(node => node.id === edge.source); const target = nodes.find(node => node.id === edge.target); return <li key={edge.id}><button type="button" onClick={() => { selectEdge(edge); setViewMode("canvas"); }}>{relationshipLabel(edge.relationship_type)} · {shortenQuestion(source?.question ?? edge.source)} ↔ {shortenQuestion(target?.question ?? edge.target)}</button></li>; })}</ul></div>}
    </>}
  </section>;
}
