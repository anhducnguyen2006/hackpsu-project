import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { DatasetCardData, DatasetGraphResponse, ResearchInterpretation, DatasetAnalysisResponse } from '../types';
import { adaptEvidence } from '../graph/adapters';
import { graphSession, newSession, type GraphSession, type SessionAction } from '../graph/graphSession';
import { project } from '../graph/projection';
import type { GraphHandle } from '../graph/SigmaGraph';
import { GraphControls } from '../graph/GraphControls';
import { GraphFilters } from '../graph/GraphFilters';
import { GraphInspector } from '../graph/GraphInspector';
import { GraphEvidenceList } from '../graph/GraphEvidenceList';
import { GraphBoundary } from '../graph/GraphBoundary';
import '../styles/graph.css';
const SigmaGraph = lazy(() => import('../graph/SigmaGraph').then(m => ({ default: m.SigmaGraph })));
const hasWebGL = () => typeof WebGL2RenderingContext !== 'undefined';
type Props = {
  graph: DatasetGraphResponse | null; datasets: DatasetCardData[]; loading?: boolean; error?: string;
  question?: string; generation?: number; cached?: boolean; interpretation?: ResearchInterpretation | null;
  keyword?: boolean; analysis?: DatasetAnalysisResponse | null; onAnalyze?: (id: string) => void;
  analysisLoading?: boolean; analysisError?: string; onRetry?: () => void; sessionRef?: React.MutableRefObject<GraphSession>;
};
export function DatasetGraph({ graph, datasets, loading = false, error = '', question = 'Research question', generation = 0,
  cached = false, interpretation, keyword, analysis, onAnalyze, analysisLoading, analysisError, onRetry, sessionRef }: Props) {
  const local = useRef(newSession()), retained = sessionRef ?? local;
  const [session, setSession] = useState(retained.current);
  const [query, setQuery] = useState(''), [list, setList] = useState(false);
  const [failure, setFailure] = useState(!hasWebGL());
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);
  const canvas = useRef<GraphHandle>(null), region = useRef<HTMLElement>(null), card = useRef<HTMLDivElement>(null);
  const context = useRef<HTMLDivElement>(null), origin = useRef<HTMLElement | null>(null);
  const snapshot = useMemo(() => adaptEvidence({ graph, datasets, question, generation, cached, interpretation, analysis, keyword }),
    [graph, datasets, question, generation, cached, interpretation, analysis, keyword]);
  const dispatch = useCallback((action: SessionAction) => setSession(s => {
    const next = graphSession(s, action); retained.current = next; return next;
  }), [retained]);
  const projection = useMemo(() => project(snapshot, session), [snapshot, session]);
  useEffect(() => {
    const m = window.matchMedia?.('(prefers-reduced-motion: reduce)'); if (!m) return;
    const change = () => setReduced(m.matches); m.addEventListener('change', change);
    return () => m.removeEventListener('change', change);
  }, []);
  useEffect(() => { if (menu) context.current?.querySelector<HTMLInputElement>('input')?.focus(); }, [menu]);
  useEffect(() => { if (session.selected) card.current?.querySelector<HTMLButtonElement>('button')?.focus(); }, [session.selected]);
  const select = (id: string) => {
    origin.current = document.activeElement as HTMLElement;
    dispatch({ type: 'select', id }); setMenu(null); setList(false); setQuery(''); canvas.current?.focus(id);
  };
  const close = () => { dispatch({ type: 'dismiss' }); (origin.current?.isConnected ? origin.current : region.current)?.focus(); };
  const graphicsFailure = useCallback(() => setFailure(true), []);
  const anchor = useCallback((point: { x: number; y: number } | null) => {
    if (!card.current || !region.current || !point) return;
    const width = region.current.clientWidth, height = region.current.clientHeight;
    const cardWidth = Math.min(300, width - 32), cardHeight = card.current.offsetHeight;
    const x = point.x + cardWidth + 32 > width ? point.x - cardWidth - 24 : point.x + 24;
    card.current.style.left = `${Math.max(16, Math.min(width - cardWidth - 16, x))}px`;
    card.current.style.top = `${Math.max(16, Math.min(height - cardHeight - 16, point.y - 24))}px`;
  }, []);
  const openMenu = (x = 20, y = 80) => {
    const bounds = region.current?.getBoundingClientRect();
    setMenu({ x: Math.max(12, Math.min(x, (bounds?.width ?? 400) - 332)), y: Math.max(12, Math.min(y, (bounds?.height ?? 600) - 420)) });
  };
  return <section ref={region} tabIndex={0} className="graph-workspace" aria-label="Scientific knowledge graph"
    aria-describedby="graph-instructions" onContextMenu={e => { e.preventDefault(); const rect = e.currentTarget.getBoundingClientRect(); openMenu(e.clientX - rect.left, e.clientY - rect.top); }}
    onKeyDown={e => {
      if (e.key === 'Escape') { setMenu(null); setList(false); close(); return; }
      if (e.target !== e.currentTarget) return;
      const moves: Record<string, [number, number]> = { ArrowLeft: [-.08, 0], ArrowRight: [.08, 0], ArrowUp: [0, -.08], ArrowDown: [0, .08] };
      if (moves[e.key]) { e.preventDefault(); canvas.current?.pan(...moves[e.key]); }
      else if (['+', '=', '-'].includes(e.key)) { e.preventDefault(); canvas.current?.zoom(e.key === '-' ? 1.3 : .77); }
      else if (e.key.toLowerCase() === 'f' && !e.shiftKey) canvas.current?.fit();
      else if (['/', 'e', 'ContextMenu'].includes(e.key) || e.key === 'F10' && e.shiftKey) { e.preventDefault(); openMenu(); }
    }}>
    <GraphBoundary fallback={null} onFailure={graphicsFailure}><Suspense fallback={null}>
      {hasWebGL() && !failure && <SigmaGraph ref={canvas} projection={projection} snapshot={snapshot} session={session}
        retained={retained.current} onSelect={select} onFailure={graphicsFailure} reduced={reduced} onAnchor={anchor} />}
    </Suspense></GraphBoundary>
    <div className="graph-heading"><h1>Graph</h1><p>{cached ? 'Cached example question' : 'Research question'}</p><p className="graph-question">{question}</p>
      <span>{projection.nodes.length} nodes · {projection.edges.length} relationships{cached ? ' · cached evidence' : ''}</span></div>
    {(loading || error || failure || analysisError) && <div className="graph-status" role="status">
      {loading && <span>Loading relationships…</span>}{error && <span>{error} {onRetry && <button onClick={onRetry}>Retry relationships</button>}</span>}
      {failure && <span>Graphics unavailable. Focus this workspace and press E to browse all evidence.</span>}{analysisError && <span>{analysisError}</span>}
    </div>}
    <p id="graph-instructions" className="graph-hint">Drag to explore · scroll to zoom · right-click or press E for evidence</p>
    <GraphFilters snapshot={snapshot} session={session} dispatch={dispatch} />
    <div className="graph-tools" aria-label="Graph actions">
      <button aria-label="Zoom in" title="Zoom in" onClick={() => canvas.current?.zoom(.77)}>+</button>
      <button aria-label="Zoom out" title="Zoom out" onClick={() => canvas.current?.zoom(1.3)}>−</button>
      <button aria-label="Fit graph" title="Fit graph (F)" onClick={() => canvas.current?.fit()}><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M9 4H4v5m11-5h5v5M4 15v5h5m11-5v5h-5"/></svg></button>
    </div>
    {session.selected && <div ref={card} className="graph-card-anchor"><GraphInspector snapshot={snapshot} session={session} datasets={datasets}
      analysis={analysis} onSelect={select} onClose={close} onAnalyze={onAnalyze} analysisLoading={analysisLoading} cached={cached} reduced={reduced} /></div>}
    {menu && <div ref={context} role="dialog" aria-label="Explore graph evidence" className="graph-context-menu graph-panel" style={{ left: menu.x, top: menu.y }}>
      <div className="graph-dialog-header"><h2>Explore evidence</h2><button aria-label="Close exploration menu" onClick={() => { setMenu(null); region.current?.focus(); }}>×</button></div>
      <GraphControls snapshot={snapshot} query={query} onQuery={setQuery} onSelect={select} />
      <div className="graph-menu-actions"><button onClick={() => { setMenu(null); setList(true); }}>Browse evidence</button>
        <button onClick={() => { dispatch({ type: 'reset' }); setMenu(null); canvas.current?.fit(); }}>Reset exploration</button>
        <button onClick={() => dispatch({ type: 'pause' })}>{session.paused ? 'Resume motion' : 'Pause motion'}</button></div>
      <p className="graph-footnote">Solid: documented. Dashed: inferred. Dotted: unverified. Graph proximity does not measure suitability or joinability.</p>
    </div>}
    {list && <div className="graph-list-layer" role="dialog" aria-label="Browse graph evidence"><button className="graph-list-close" onClick={() => { setList(false); region.current?.focus(); }}>Close evidence list</button><GraphEvidenceList snapshot={snapshot} onSelect={select} /></div>}
  </section>;
}
