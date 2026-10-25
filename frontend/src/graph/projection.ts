import type { Snapshot } from './model';
import type { GraphSession } from './graphSession';
/** Filters are explicit user choices; the initial constellation contains every loaded node. */
export function project(snapshot: Snapshot, session: GraphSession) {
  const allowedDatasets = new Set(snapshot.nodes.filter(n => n.kind === 'dataset' &&
    (session.repository === null || session.repository.includes(String(n.attributes.source)))).map(n => n.datasetId));
  const nodes = snapshot.nodes.filter(n => (!n.datasetId || allowedDatasets.has(n.datasetId)) &&
    (session.nodeType === null || session.nodeType.includes(n.kind)));
  const ids = new Set(nodes.map(n => n.id));
  const edges = snapshot.edges.filter(e => ids.has(e.source) && ids.has(e.target) &&
    (session.relationship === null || session.relationship.includes(e.relationship)) &&
    (session.evidence === null || session.evidence.includes(e.evidenceClass)));
  return { nodes, edges };
}
