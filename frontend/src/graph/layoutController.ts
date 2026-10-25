import Graph from 'graphology';
import FA2Layout from 'graphology-layout-forceatlas2/worker';
import type { EvidenceNode, Snapshot } from './model';
type Positions = Record<string, { x: number; y: number }>;
export function seedPosition(node: EvidenceNode, index: number, all: EvidenceNode[], positions: Positions) {
  if (positions[node.id]) return positions[node.id];
  if (node.kind === 'research_question') return { x: 0, y: 0 };
  // A deterministic sunflower seed avoids overlapping circles and extreme initial forces.
  const angle = index * 2.399963229728653;
  const radius = 18 * Math.sqrt(index + 1);
  if (node.kind === 'variable') {
    const owner = positions[`dataset:${node.datasetId}`];
    if (owner) {
      const siblings = all.filter(n => n.datasetId === node.datasetId && n.kind === 'variable');
      const i = siblings.findIndex(n => n.id === node.id);
      const r = 12 + 5 * Math.sqrt(i + 1);
      return { x: owner.x + Math.cos(angle) * r, y: owner.y + Math.sin(angle) * r };
    }
  }
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}
/** One simplified layout edge per pair. All semantic edges remain in the renderer. */
export function settleLayout(snapshot: Pick<Snapshot, 'nodes' | 'edges'>, apply: (p: Positions) => void,
  positions: Positions, _reduced: boolean, onSettled: () => void = () => {}) {
  const graph = new Graph({ type: 'undirected' });
  snapshot.nodes.forEach((n, i) => graph.addNode(n.id, {
    ...seedPosition(n, i, snapshot.nodes, positions), fixed: n.kind === 'research_question', size: n.kind === 'research_question' ? 4 : n.kind === 'dataset' ? 3 : 1.5,
  }));
  snapshot.edges.forEach(e => {
    if (graph.hasNode(e.source) && graph.hasNode(e.target) && e.source !== e.target && !graph.hasEdge(e.source, e.target)) graph.addEdge(e.source, e.target);
  });
  let worker: FA2Layout | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;
  const publish = () => {
    const result: Positions = {};
    graph.forEachNode((id, a) => { if (Number.isFinite(a.x) && Number.isFinite(a.y)) result[id] = { x: a.x, y: a.y }; });
    apply(result);
  };
  const stop = (complete = false) => {
    if (stopped) return;
    stopped = true;
    clearTimeout(timer);
    worker?.stop(); publish(); worker?.kill();
    if (complete) onSettled();
  };
  if (typeof Worker !== 'undefined' && graph.order > 1) {
    worker = new FA2Layout(graph, { settings: { gravity: 0.8, strongGravityMode: true, scalingRatio: 4, slowDown: 12, adjustSizes: true, barnesHutOptimize: true } });
    worker.start(); timer = setTimeout(() => stop(true), 1200);
  } else { publish(); onSettled(); }
  return { stop: () => stop(), kill: () => stop() };
}
