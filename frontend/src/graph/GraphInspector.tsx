import { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import type { Snapshot } from './model';
import type { GraphSession } from './graphSession';
import type { DatasetAnalysisResponse, DatasetCardData, ColumnProfile } from '../types';
gsap.registerPlugin(useGSAP);
export function GraphInspector({ snapshot, session, datasets, analysis, onSelect, onClose, onAnalyze, analysisLoading, cached, reduced }: {
  snapshot: Snapshot; session: GraphSession; datasets: DatasetCardData[]; analysis?: DatasetAnalysisResponse | null;
  onSelect: (id: string) => void; onClose: () => void; onAnalyze?: (id: string) => void; analysisLoading?: boolean; cached: boolean; reduced: boolean;
}) {
  const root = useRef<HTMLElement>(null);
  const node = snapshot.nodes.find(n => n.id === session.selected), edge = snapshot.edges.find(e => e.id === session.selected);
  const dataset = datasets.find(d => d.dataset_id === node?.datasetId);
  const provenance = node?.provenance ?? edge?.provenance;
  const relations = snapshot.edges.filter(e => e.source === node?.id || e.target === node?.id);
  const profile = node?.attributes.profile as ColumnProfile | undefined;
  useGSAP(() => { if (root.current && !reduced) gsap.from(root.current, { opacity: 0, y: 8, duration: .2, ease: 'power2.out' }); },
    { scope: root, dependencies: [session.selected], revertOnUpdate: true });
  return <aside ref={root} className="graph-inspector graph-panel" aria-label="Evidence inspector">
    <button className="graph-close" aria-label="Close inspector" onClick={onClose}>×</button>
    <p className="graph-meta">{node?.kind.replace(/_/g, ' ') ?? 'Relationship'}{cached ? ' · cached' : ''}</p>
    <h2>{node?.label ?? edge?.relationship}</h2>
    {node?.datasetId && <p className="graph-meta">{node.datasetId}</p>}
    {dataset && <p className="graph-card-description">{dataset.description ?? 'Description unavailable.'}</p>}
    {edge && <><p className="graph-evidence-class">{edge.evidenceClass.replace(/_/g, ' ')}</p>
      <dl className="graph-edge-facts">
        <dt>Source</dt><dd><button onClick={() => onSelect(edge.source)}>{snapshot.nodes.find(n => n.id === edge.source)?.label ?? edge.source}</button></dd>
        <dt>Target</dt><dd><button onClick={() => onSelect(edge.target)}>{snapshot.nodes.find(n => n.id === edge.target)?.label ?? edge.target}</button></dd>
        <dt>Verification status</dt><dd>{edge.rawVerificationStatus ?? 'Not supplied'}</dd>
        <dt>Provenance</dt><dd>{edge.provenance.origin}{edge.provenance.fieldPaths.length > 0 && ` · ${edge.provenance.fieldPaths.join(', ')}`}</dd>
        <dt>Supporting evidence</dt><dd>{edge.provenance.evidenceText || 'Evidence text unavailable.'}</dd>
      </dl></>}
    {provenance?.sourceRecordUrls.map(url => <a className="graph-source-link" key={url} href={url} target="_blank" rel="noreferrer">Source record ↗</a>)}
    {profile && <p>{cached ? 'Cached computed profile' : 'Computed profile'}: {profile.missing_count} missing; {profile.unique_count} unique values.</p>}
    <details><summary>Evidence & provenance{relations.length ? ` · ${relations.length} relations` : ''}</summary>
      {provenance && <><p>{provenance.evidenceText}</p><dl><dt>Origin</dt><dd>{provenance.origin}</dd><dt>Source fields</dt><dd>{provenance.fieldPaths.join(', ') || 'Not supplied'}</dd><dt>Source verification time</dt><dd>Unavailable</dd></dl></>}
      {edge && <dl><dt>Returned relationship</dt><dd>{edge.rawRelationshipType ?? edge.relationship}</dd><dt>Returned verification status</dt><dd>{edge.rawVerificationStatus ?? 'Not supplied'}</dd></dl>}
      {dataset && <dl><dt>Repository</dt><dd>{dataset.source}</dd><dt>Variables</dt><dd>{dataset.variables.length} documented</dd><dt>Scientific suitability</dt><dd>{analysis?.dataset.dataset_id === dataset.dataset_id && analysis.assessment ? 'Available in analysis' : 'Unavailable'}</dd></dl>}
      <ul className="graph-relations">{relations.map(e => <li key={e.id}><button onClick={() => onSelect(e.id)}>{e.relationship}<small>{e.evidenceClass.replace(/_/g, ' ')}</small></button></li>)}</ul>
    </details>
    {onAnalyze && dataset?.dataset_id.startsWith('uci:') && (!cached || dataset.dataset_id === 'uci:320') &&
      <button className="graph-analyze" disabled={analysisLoading} onClick={() => onAnalyze(dataset.dataset_id)}>{analysisLoading ? 'Analyzing…' : cached ? 'Open analysis preview' : 'Analyze dataset'}</button>}
  </aside>;
}
