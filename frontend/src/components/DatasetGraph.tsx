import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type { DatasetCardData, DatasetGraphEdgeData, DatasetGraphNodeData, DatasetGraphResponse } from "../types";

type DatasetGraphProps = {
  graph: DatasetGraphResponse | null;
  datasets: DatasetCardData[];
  loading?: boolean;
  error?: string;
};

const NODE_TYPES = ["DATASET", "VARIABLE", "GEOGRAPHY", "TIME_PERIOD", "RESEARCH_CONCEPT"];

function nodeTypeLabel(type: string) {
  return type === "TIME_PERIOD" ? "Time period" : type === "RESEARCH_CONCEPT" ? "Research concept" : type.charAt(0) + type.slice(1).toLowerCase();
}

function isMetadataNode(node: DatasetGraphNodeData) {
  return ["VARIABLE", "GEOGRAPHY", "TIME_PERIOD"].includes(node.type);
}

export function DatasetGraph({ graph, datasets, loading = false, error = "" }: DatasetGraphProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<DatasetGraphNodeData | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<DatasetGraphEdgeData | null>(null);
  const [nodeFilter, setNodeFilter] = useState("all");
  const [edgeFilter, setEdgeFilter] = useState("all");
  const [expandedDatasetId, setExpandedDatasetId] = useState<string | null>(null);
  const graphNodes = graph?.nodes ?? [];
  const graphEdges = graph?.edges ?? [];

  const datasetByNodeId = useMemo(() => new Map(datasets.map((dataset) => [`dataset:${dataset.dataset_id}`, dataset])), [datasets]);
  const edgeTypes = useMemo(() => [...new Set(graphEdges.map(({ data }) => data.relationship_type))].sort(), [graphEdges]);

  const visibleGraph = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    const visibleNodes = graphNodes.filter(({ data }) => {
      const matchesFilter = nodeFilter === "all" || data.type === nodeFilter;
      const metadataIsExpanded = expandedDatasetId !== null && isMetadataNode(data) && graphEdges.some(({ data: edge }) => (edge.source === expandedDatasetId && edge.target === data.id) || (edge.target === expandedDatasetId && edge.source === data.id));
      const isFocused = data.type === "DATASET" || data.type === "RESEARCH_CONCEPT" || metadataIsExpanded;
      return matchesFilter && isFocused;
    });
    const visibleNodeIds = new Set(visibleNodes.map(({ data }) => data.id));
    const visibleEdges = graphEdges.filter(({ data }) => {
      if (edgeFilter !== "all" && data.relationship_type !== edgeFilter) return false;
      if (!visibleNodeIds.has(data.source) || !visibleNodeIds.has(data.target)) return false;
      return expandedDatasetId !== null || !isMetadataNode(graphNodes.find(({ data: node }) => node.id === data.source)?.data ?? { type: "" } as DatasetGraphNodeData) && !isMetadataNode(graphNodes.find(({ data: node }) => node.id === data.target)?.data ?? { type: "" } as DatasetGraphNodeData);
    });
    return { nodes: visibleNodes, edges: visibleEdges };
  }, [edgeFilter, expandedDatasetId, graph, graphEdges, graphNodes, nodeFilter]);

  useEffect(() => {
    if (!containerRef.current || loading || error || graphNodes.length === 0) return;
    cyRef.current?.destroy();
    const elements = [
      ...visibleGraph.nodes.map(({ data }) => ({ data })),
      ...visibleGraph.edges.map(({ data }) => ({ data })),
    ];
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      layout: { name: "cose", animate: false, padding: 36, fit: true },
      style: [
        { selector: "node", style: { label: "data(label)", color: "#201C24", "font-family": "Georgia, serif", "font-size": "13px", "text-wrap": "wrap", "text-max-width": "125px", "text-valign": "center", "text-halign": "center", width: 34, height: 34, "border-width": 2, "border-color": "#F6F7F6" } },
        { selector: 'node[type="DATASET"]', style: { backgroundColor: "#3d8c65", shape: "round-rectangle", width: 54, height: 54, "font-size": "14px", "font-weight": 700 } },
        { selector: 'node[type="VARIABLE"]', style: { backgroundColor: "#8b63b7", shape: "ellipse" } },
        { selector: 'node[type="GEOGRAPHY"]', style: { backgroundColor: "#d36b45", shape: "ellipse" } },
        { selector: 'node[type="TIME_PERIOD"]', style: { backgroundColor: "#eaaa00", shape: "ellipse" } },
        { selector: 'node[type="RESEARCH_CONCEPT"]', style: { backgroundColor: "#477bb5", shape: "ellipse" } },
        { selector: "edge", style: { label: "data(relationship_type)", width: 1.5, "line-color": "#aeb8c0", "target-arrow-color": "#aeb8c0", "target-arrow-shape": "triangle", "curve-style": "bezier", color: "#5f6269", "font-family": "ui-monospace, monospace", "font-size": "8px", "text-background-color": "#f6f7f6", "text-background-opacity": 0.9, "text-rotation": "autorotate" } },
        { selector: 'edge[verification_status = "verified_metadata"]', style: { "line-color": "#3d8c65", "target-arrow-color": "#3d8c65" } },
        { selector: 'edge[verification_status = "unverified_potential"]', style: { "line-style": "dashed", "line-color": "#d36b45", "target-arrow-color": "#d36b45" } },
        { selector: ".is-selected", style: { "border-color": "#eaaa00", "border-width": 4 } },
      ],
    });
    cy.on("tap", "node", (event) => {
      const node = event.target.data() as DatasetGraphNodeData;
      selectNode(node);
    });
    cy.on("tap", "edge", (event) => {
      setSelectedEdge(event.target.data() as DatasetGraphEdgeData);
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
  }, [error, graphNodes.length, loading, visibleGraph]);

  function fitGraph() { cyRef.current?.fit(undefined, 36); }
  function resetGraph() { setExpandedDatasetId(null); setSelectedNode(null); setSelectedEdge(null); fitGraph(); }
  function selectNode(node: DatasetGraphNodeData) {
    setSelectedNode(node);
    setSelectedEdge(null);
    if (node.type === "DATASET") {
      setExpandedDatasetId(node.id);
      cyRef.current?.elements().removeClass("is-selected");
      cyRef.current?.$id(node.id).addClass("is-selected");
    }
  }

  const selectedDataset = selectedNode?.type === "DATASET" ? datasetByNodeId.get(selectedNode.id) : undefined;
  const relatedDatasets = selectedDataset ? graphEdges.filter(({ data }) => data.source === selectedNode?.id || data.target === selectedNode?.id).map(({ data }) => data.source === selectedNode?.id ? data.target : data.source).filter((id) => id.startsWith("dataset:") && id !== selectedNode?.id).map((id) => datasetByNodeId.get(id)).filter((dataset): dataset is DatasetCardData => Boolean(dataset)) : [];

  return <section className="dataset-graph" aria-label="Dataset relationship graph">
    <div className="graph-toolbar">
      <div><span className="data-label">Graph view</span><h1 className="graph-title">Graph</h1><p className="graph-toolbar-note">Datasets and key relationships are shown first. Select a dataset to expand verified metadata.</p></div>
      <div className="graph-actions"><button type="button" className="secondary-action" onClick={fitGraph} disabled={!graphNodes.length}>Fit graph</button><button type="button" className="secondary-action" onClick={resetGraph} disabled={!expandedDatasetId}>Reset focus</button></div>
    </div>
    <div className="graph-filters" aria-label="Graph filters"><label>Node type<select value={nodeFilter} onChange={(event) => setNodeFilter(event.target.value)}><option value="all">All node types</option>{NODE_TYPES.map((type) => <option key={type} value={type}>{nodeTypeLabel(type)}</option>)}</select></label><label>Relationship<select value={edgeFilter} onChange={(event) => setEdgeFilter(event.target.value)}><option value="all">All relationships</option>{edgeTypes.map((type) => <option key={type} value={type}>{type.replace(/_/g, " ")}</option>)}</select></label></div>
    {loading ? <div className="graph-empty" role="status"><h2>Loading graph</h2><p>Fetching verified relationships for this research question.</p></div> : error ? <div className="graph-empty graph-error" role="alert"><h2>Graph unavailable</h2><p>{error}</p></div> : graphNodes.length === 0 ? <div className="graph-empty" role="status"><h2>No graph data yet</h2><p>Run a live discovery search to load repository-backed dataset relationships.</p></div> : <div className="graph-layout"><div className="graph-stage"><div ref={containerRef} className="cytoscape-canvas" role="img" aria-label="Interactive dataset relationship graph" tabIndex={0} /><div className="graph-legend"><span><i className="graph-key dataset" />Dataset</span><span><i className="graph-key variable" />Variable</span><span><i className="graph-key geography" />Geography</span><span><i className="graph-key time" />Time period</span><span><i className="graph-key concept" />Research concept</span></div><div className="graph-node-index" aria-label="Dataset nodes"><span className="data-label">Dataset nodes</span>{visibleGraph.nodes.filter(({ data }) => data.type === "DATASET").map(({ data }) => <button type="button" key={data.id} className="graph-node-button" onClick={() => selectNode(data)}>{data.label}</button>)}</div></div><aside className="graph-detail" aria-live="polite">{selectedDataset ? <><span className="data-label">Selected dataset</span><h2>{selectedDataset.title}</h2><p>{selectedDataset.description ?? "Description unavailable."}</p><dl className="graph-detail-list"><div><dt>Source</dt><dd>{selectedDataset.source}</dd></div><div><dt>Verified variables</dt><dd>{selectedDataset.variables.length ? selectedDataset.variables.join(", ") : "Not documented"}</dd></div><div><dt>Coverage</dt><dd>{[...(selectedDataset.geographic_coverage ?? []), ...(selectedDataset.temporal_coverage ?? [])].join(", ") || "Not documented"}</dd></div></dl><a href={selectedDataset.landing_page_url ?? selectedDataset.repository_url} target="_blank" rel="noreferrer">Open source record</a>{relatedDatasets.length > 0 && <div className="graph-related"><span className="data-label">Related datasets</span><ul>{relatedDatasets.map((dataset) => <li key={dataset.dataset_id}>{dataset.title}</li>)}</ul></div>}</> : selectedEdge ? <><span className="data-label">Selected relationship</span><h2>{selectedEdge.relationship_type.replace(/_/g, " ")}</h2><p>{selectedEdge.evidence}</p><dl className="graph-detail-list"><div><dt>Supporting metadata</dt><dd>{selectedEdge.evidence}</dd></div><div><dt>Verification status</dt><dd>{selectedEdge.verification_status.replace(/_/g, " ")}</dd></div></dl></> : <><span className="data-label">Graph inspector</span><h2>Select a node or relationship</h2><p>Dataset nodes open verified source metadata. Relationships show the evidence and verification status returned by the backend.</p></>}</aside></div>}
  </section>;
}
