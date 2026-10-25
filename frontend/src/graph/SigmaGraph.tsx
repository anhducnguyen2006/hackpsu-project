import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import Graph from 'graphology';
import Sigma from 'sigma';
import { layerDashed, layerFill } from 'sigma/rendering';
import type { Snapshot, EvidenceNode } from './model';
import type { GraphSession } from './graphSession';
import { seedPosition, settleLayout } from './layoutController';
import { placeLabels } from './labelPolicy';
export interface GraphHandle {
  fit(): void; zoom(factor: number): void; pan(x: number, y: number): void; focus(id: string): void;
}
export const colors: Record<EvidenceNode['kind'], string> = {
  research_question: '#B77A08', dataset: '#287F8C', variable: '#657786', concept: '#79609C', domain: '#77718B', geography: '#657786', time_period: '#657786',
};
type Projection = Pick<Snapshot, 'nodes' | 'edges'>;
type Props = { projection: Projection; snapshot: Snapshot; session: GraphSession; retained: GraphSession;
  onSelect: (id: string) => void; onFailure: () => void; reduced: boolean;
  onAnchor: (p: { x: number; y: number } | null) => void };

// Lit spheres use the same native GPU fill pipeline, with a fixed soft light at upper left.
function constellationEdges() {
  const layer = layerDashed({dashSize:{attribute:'dash',default:10000,mode:'pixels'},gapSize:{attribute:'gap',default:0,mode:'pixels'}});
  // Sigma's dashed layer expects a plain layer underneath for zero-gap edges.
  // This single-layer variant returns the solid color for that case.
  return {...layer, glsl:layer.glsl.replace('if (dashSize < dashThreshold || gapSize < dashThreshold) {\n    return vec4(0.0);', 'if (dashSize < dashThreshold || gapSize < dashThreshold) {\n    return dashColor;')};
}
function sphereFill() {
  const fill = layerFill();
  return { ...fill, glsl: fill.glsl.replace('return v_fillColor;', `
    vec2 p = context.uv / max(context.shapeSize, 0.001);
    float z = sqrt(max(0.0, 1.0 - dot(p, p)));
    vec3 normal = normalize(vec3(p.x, -p.y, z));
    float light = max(0.0, dot(normal, normalize(vec3(-0.5, 0.65, 1.0))));
    float spec = pow(max(0.0, dot(normal, normalize(vec3(-0.3, 0.45, 1.0)))), 22.0);
    vec3 color = v_fillColor.rgb * (0.67 + 0.34 * light);
    color = mix(color, vec3(1.0), 0.42 * spec);
    return vec4(color, v_fillColor.a);`) };
}
export const SigmaGraph = forwardRef<GraphHandle, Props>(function SigmaGraph(props, ref) {
  const container = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const ready = useRef(false);
  const settledIds = useRef(new Set<string>());
  const initialCamera = useRef(props.retained.camera);
  const glow = useRef<HTMLDivElement>(null);
  const selectedGlow = useRef<HTMLDivElement>(null);
  const tooltip = useRef<HTMLDivElement>(null);
  const labelLayer = useRef<HTMLDivElement>(null);
  const labelElements = useRef(new Map<string, HTMLButtonElement>());
  const renderer = useRef<Sigma | null>(null);
  const graph = useRef(new Graph({ multi: true, type: 'directed' }));
  const layout = useRef<ReturnType<typeof settleLayout>>();
  const current = useRef(props); current.current = props;
  const hover = useRef<string | null>(null);
  const hoveredEdge = useRef<string | null>(null);
  const focusedLabel = useRef<string | null>(null);
  const fitRef = useRef<() => void>(() => {});
  const labelsRef = useRef<() => void>(() => {});
  const emphasisRef = useRef<() => void>(() => {});
  const overlaysRef = useRef<() => void>(() => {});
  const hoverNode = (id: string | null) => {
    hover.current = id; hoveredEdge.current = null;
    emphasisRef.current(); overlaysRef.current();
  };
  const changeCamera = (next: Partial<{ x: number; y: number; ratio: number; angle: number }>, duration = 400) => {
    const c = renderer.current?.getCamera(); c?.cancelAnimation();
    if (!ready.current || current.current.reduced || current.current.session.paused) c?.setState(next);
    else void c?.animate(next, { duration });
  };
  useImperativeHandle(ref, () => ({
    fit() { layout.current?.stop(); fitRef.current(); },
    zoom(factor) { layout.current?.stop(); const c = renderer.current?.getCamera(); if (c) changeCamera({ ratio: c.ratio * factor }, 220); },
    pan(x, y) { layout.current?.stop(); const c = renderer.current?.getCamera(); if (c) changeCamera({ x: c.x + x * c.ratio, y: c.y + y * c.ratio }); },
    focus(id) {
      layout.current?.stop(); const r = renderer.current; const g = graph.current;
      if (!r || !g.hasNode(id)) return;
      const p = r.graphToFramedGraph(g.getNodeAttributes(id) as { x: number; y: number });
      // Preserve the user's zoom while bringing the node to a comfortable inspection position.
      changeCamera(p);
    },
  }), []);
  useEffect(() => {
    const host = container.current; if (!host) return;
    let r: Sigma | null = null; let observer: ResizeObserver | undefined; let frame = 0; let releaseCursor = () => {};
    const g = graph.current;
    try {
      r = new Sigma(g, host, {
        settings: { autoRescale: 'once', autoRescaleContent: 'labels', itemSizesReference: 'screen', zoomToSizeRatioFunction: () => 1, enableNodeDrag: true, enableEdgeEvents: true,
          renderEdgeLabels: false, renderLabels: false, nodeLabelEvents: 'extend', edgePickingPadding: 5, stagePadding: 48,
          inertiaDuration: props.reduced ? 0 : 100, zoomDuration: props.reduced ? 0 : 180, minCameraRatio: 0.02, maxCameraRatio: 15 },
        primitives: { nodes: { layers: [sphereFill()] }, edges: { variables: { dash: {type:'number',default:10000}, gap: {type:'number',default:0} }, layers: [constellationEdges()] } },
        styles: {
          nodes: { cursor: 'pointer', x: { attribute: 'x' }, y: { attribute: 'y' }, color: { attribute: 'color' }, size: { attribute: 'size' }, label: { attribute: 'displayLabel' },
            labelFont: '12px Geist', labelSize: 12, labelColor: '#3A0F34', labelVisibility: { attribute: 'labelVisibility', defaultValue: 'hidden' },
            opacity: { attribute: 'opacity', defaultValue: 1 }, backdropVisibility: 'hidden' },
          edges: { cursor:'pointer', color: {attribute:'color',defaultValue:'#7F7888'}, size: 0.8, opacity: { attribute: 'opacity', defaultValue: 0.48 }, parallelSpread: { attribute: 'spread', defaultValue: 0 } },
        },
      });
      renderer.current = r;
      const mouse = r.getMouseLayer();
      mouse.style.cursor = 'grab';
      let dragging = false;
      const cursor = () => { mouse.style.cursor = dragging ? 'grabbing' : hover.current || hoveredEdge.current ? 'pointer' : 'grab'; };
      const release = () => { dragging = false; cursor(); };
      mouse.addEventListener('pointerdown', () => { dragging = true; cursor(); });
      window.addEventListener('pointerup', release);
      window.addEventListener('pointercancel', release);
      releaseCursor = () => { window.removeEventListener('pointerup', release); window.removeEventListener('pointercancel', release); };
      r.on('enterNode', () => cursor());
      r.on('leaveNode', () => { hover.current = null; cursor(); });
      r.on('nodeDragStart', () => { dragging = true; cursor(); });
      r.on('nodeDragEnd', release);
      r.on('afterRender', cursor);
      const measure = document.createElement('canvas').getContext('2d'); if (measure) measure.font = '12px Geist';
      const labels = () => {
        if (!r) return;
        const { session } = current.current;
        const firstLabel = labelElements.current.values().next().value;
        if (measure && firstLabel) measure.font = getComputedStyle(firstLabel).font;
        const anchors = g.nodes().map(id => {
          const a = g.getNodeAttributes(id), element = labelElements.current.get(id);
          const p = r!.graphToViewport(a as {x:number;y:number});
          return {id,...p,radius:r!.scaleSize(a.size),
            width:Math.min(220,Math.ceil((measure?.measureText(a.displayLabel).width ?? a.displayLabel.length*7)+8)),
            height:element?.offsetHeight || 20};
        });
        const placements = placeLabels(anchors,host.clientWidth,host.clientHeight);
        for (const [id, box] of placements) {
          const element = labelElements.current.get(id); if (!element) continue;
          element.hidden = false;
          element.setAttribute('aria-pressed', String(id === session.selected));
          element.style.transform = `translate(${box.x}px,${box.y}px)`;
          element.style.maxWidth = `${box.width}px`;
          // Keep every name readable while the nodes and edges convey hover emphasis.
          element.style.opacity = '1';
        }
      }; labelsRef.current = labels;
      const emphasis = () => {
        const active = hover.current ?? focusedLabel.current ?? hoveredEdge.current ?? current.current.session.focus ?? current.current.session.selected;
        const neighborhood = new Set(active && g.hasNode(active) ? [active, ...g.neighbors(active)] : active && g.hasEdge(active) ? g.extremities(active) : []);
        g.forEachNode(id => { const value = neighborhood.size && !neighborhood.has(id) ? 0.2 : 1;
          if (g.getNodeAttribute(id, 'opacity') !== value) g.setNodeAttribute(id, 'opacity', value); });
        g.forEachEdge((id, a, source, target) => {
          const connected = source === active || target === active || id === active;
          const opacity = active ? connected ? 0.85 : 0.08 : 0.48;
          if (a.opacity !== opacity) g.mergeEdgeAttributes(id, { opacity, spread: connected ? 10 : 0 });
        }); labels();
      }; emphasisRef.current = emphasis;
      const overlays = () => {
        if (!r) return;
        const { snapshot, session } = current.current;
        const position = (id: string | null) => id && g.hasNode(id) ? r!.graphToViewport(g.getNodeAttributes(id) as { x: number; y: number }) : null;
        const q = snapshot.nodes.find(n => n.kind === 'research_question');
        for (const [element, p] of [[glow.current, position(q?.id ?? null)], [selectedGlow.current, position(hover.current ?? session.selected)]] as const) {
          if (!element) continue; element.hidden = !p;
          if (p) element.style.transform = `translate(${p.x}px,${p.y}px)`;
        }
        const edge = snapshot.edges.find(e => e.id === hoveredEdge.current);
        const source = edge && position(edge.source), target = edge && position(edge.target);
        const p = source && target ? {x:(source.x+target.x)/2,y:(source.y+target.y)/2} : null;
        if (tooltip.current) {
          tooltip.current.hidden = !p;
          if (p) { tooltip.current.textContent = edge ? `${edge.relationship} · ${edge.evidenceClass.replace(/_/g,' ')}` : ''; tooltip.current.style.left = `${Math.max(12, Math.min(host.clientWidth - 250, p.x + 16))}px`; tooltip.current.style.top = `${Math.max(12, Math.min(host.clientHeight - 70, p.y + 14))}px`; }
        }
        let anchor = position(session.selected);
        if (!anchor && session.selected && g.hasEdge(session.selected)) { const a = position(g.source(session.selected)), b = position(g.target(session.selected)); if (a && b) anchor = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }; }
        current.current.onAnchor(anchor); labels();
      }; overlaysRef.current = overlays;
      const fit = () => {
        if (!r || !g.order || !host.clientWidth || !host.clientHeight) return;
        r.resize();
        let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
        g.forEachNode((_, a) => { xMin = Math.min(xMin, a.x); xMax = Math.max(xMax, a.x); yMin = Math.min(yMin, a.y); yMax = Math.max(yMax, a.y); });
        if (xMin === xMax) { xMin -= 1; xMax += 1; } if (yMin === yMax) { yMin -= 1; yMax += 1; }
        r.setCustomBBox({ x: [xMin, xMax], y: [yMin, yMax] }); r.refresh();
        // Fit in viewport space so wide and tall screens both use their available area.
        let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
        g.forEachNode((_, a) => { const p = r!.graphToViewport(a as { x: number; y: number }); const radius = r!.scaleSize(a.size);
          const labelWidth = Math.min(180, measure?.measureText(a.displayLabel).width ?? 100);
          left = Math.min(left, p.x - radius - 5); right = Math.max(right, p.x + radius + labelWidth + 8);
          top = Math.min(top, p.y - radius - 10); bottom = Math.max(bottom, p.y + radius + 10); });
        const padding = host.clientWidth < 768 ? 24 : 50;
        const scale = Math.min((host.clientWidth - padding * 2) / Math.max(1, right - left), (host.clientHeight - padding * 2) / Math.max(1, bottom - top));
        const center = r.viewportToFramedGraph({ x: (left + right) / 2, y: (top + bottom) / 2 });
        changeCamera({ ...center, angle: 0, ratio: r.getCamera().ratio / Math.max(0.01, scale) });
        labels(); overlays();
      }; fitRef.current = fit;
      r.on('clickNode', ({ node }) => current.current.onSelect(node));
      r.on('clickEdge', ({ edge }) => current.current.onSelect(edge));
      r.on('enterNode', ({ node }) => { hoverNode(node); cursor(); });
      r.on('leaveNode', () => { hoverNode(null); cursor(); });
      r.on('enterEdge', ({ edge }) => { hoveredEdge.current = edge; hover.current = null; emphasis(); overlays(); cursor(); });
      r.on('leaveEdge', () => { hoveredEdge.current = null; emphasis(); overlays(); cursor(); });
      r.on('doubleClickStage', ({ event }) => { event.preventSigmaDefault(); layout.current?.stop(); fit(); });
      r.on('nodeDragStart', () => { layout.current?.stop(); r?.getCamera().cancelAnimation(); });
      r.on('downStage', () => { layout.current?.stop(); r?.getCamera().cancelAnimation(); });
      r.on('nodeDragEnd', () => { g.forEachNode((id, a) => { current.current.retained.positions[id] = { x: a.x, y: a.y }; }); });
      r.on('webglContextLost', () => { layout.current?.kill(); current.current.onFailure(); });
      r.getCamera().on('updated', () => { labels(); overlays(); });
      r.on('afterRender', () => { current.current.retained.camera = r!.getCamera().getState(); overlays(); });
      observer = new ResizeObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => {if(ready.current)fit();}); }); observer.observe(host);
      if (props.retained.camera) r.getCamera().setState(props.retained.camera);
    } catch (error) {
      console.warn('Graph renderer could not initialize.', error);
      r?.kill(); renderer.current = null; current.current.onFailure();
    }
    return () => { releaseCursor(); observer?.disconnect(); cancelAnimationFrame(frame); layout.current?.kill();
      g.forEachNode((id, a) => { current.current.retained.positions[id] = { x: a.x, y: a.y }; });
      r?.kill(); renderer.current = null;
    };
  }, []);
  useEffect(() => {
    const r = renderer.current; if (!r) return; const g = graph.current;
    const ids = new Set(props.projection.nodes.map(n => n.id)), edgeIds = new Set(props.projection.edges.map(e => e.id));
    g.edges().forEach(id => { if (!edgeIds.has(id)) g.dropEdge(id); });
    g.nodes().forEach(id => { if (!ids.has(id)) g.dropNode(id); });
    for (const [id, element] of labelElements.current) if (!ids.has(id)) {element.remove();labelElements.current.delete(id);}
    props.projection.nodes.forEach((n, i) => {
      const attrs = { color: colors[n.kind], size: n.kind === 'research_question' ? 19 : n.kind === 'dataset' ? 12.5 : n.kind === 'variable' ? 6.2 : 9,
        displayLabel: n.kind === 'research_question' ? 'Research question' : n.label.length > 34 ? `${n.label.slice(0,32)}…` : n.label };
      if (!labelElements.current.has(n.id) && labelLayer.current) {
        // Permanent DOM labels avoid Sigma 4's GPU label-picking issue.
        // Mirror nodeLabelEvents="extend" and add native keyboard activation.
        const element = document.createElement('button'); element.type = 'button'; element.className = 'graph-node-label'; element.hidden = true;
        element.addEventListener('pointerenter', () => hoverNode(n.id));
        element.addEventListener('pointerleave', () => hoverNode(null));
        element.addEventListener('focus', () => { focusedLabel.current = n.id; hoverNode(n.id); });
        element.addEventListener('blur', () => { focusedLabel.current = null; hoverNode(null); });
        element.addEventListener('click', e => { e.stopPropagation(); current.current.onSelect(n.id); });
        element.addEventListener('wheel', e => {
          e.preventDefault(); renderer.current?.getMouseLayer().dispatchEvent(new WheelEvent('wheel', e));
        }, {passive:false});
        labelLayer.current.appendChild(element); labelElements.current.set(n.id, element);
      }
      const label = labelElements.current.get(n.id);
      if (label) { label.textContent = attrs.displayLabel; label.setAttribute('aria-label', `Inspect ${n.label}`); }
      if (g.hasNode(n.id)) g.mergeNodeAttributes(n.id, attrs);
      else { const p = seedPosition(n, i, props.snapshot.nodes, props.retained.positions); g.addNode(n.id, { ...p, ...attrs }); props.retained.positions[n.id] = p; }
    });
    props.projection.edges.forEach(e => {
      const attrs = { color:e.evidenceClass === 'inferred' ? '#82699C' : '#7F7888', dash: e.evidenceClass === 'unverified' ? 1 : e.evidenceClass === 'inferred' ? 5 : 10000,
        gap: e.evidenceClass === 'unverified' ? 4 : e.evidenceClass === 'inferred' ? 4 : 0 };
      if (g.hasEdge(e.id)) g.mergeEdgeAttributes(e.id, attrs); else g.addEdgeWithKey(e.id, e.source, e.target, attrs);
    });
    r.refresh(); labelsRef.current(); emphasisRef.current();
  }, [props.projection, props.snapshot, props.session]);
  const topology = props.projection.nodes.map(n => n.id).join('|');
  useEffect(() => {
    if (!renderer.current || !props.projection.nodes.length) return;
    const nodes = props.projection.nodes;
    // Returning visits and filter changes reuse established coordinates and never restart physics.
    if (initialCamera.current || nodes.every(n => settledIds.current.has(n.id))) {
      ready.current = true;
      stage.current?.classList.add('is-ready');
      if (initialCamera.current) { renderer.current.getCamera().setState(initialCamera.current); initialCamera.current = undefined; }
      // Explicit filters reuse the camera as well as established coordinates.
      nodes.forEach(n => settledIds.current.add(n.id));
      return;
    }
    ready.current = false;
    stage.current?.classList.remove('is-ready');
    const frame = requestAnimationFrame(() => {
      const complete = () => {
        // Camera normalization and bounds are applied once, before the first visible frame.
        fitRef.current();
        nodes.forEach(n => settledIds.current.add(n.id));
        ready.current = true;
        stage.current?.classList.add('is-ready');
      };
      if (current.current.session.paused) { complete(); return; }
      layout.current = settleLayout(current.current.projection, positions => {
        for (const [id, p] of Object.entries(positions)) {
          if (graph.current.hasNode(id)) graph.current.mergeNodeAttributes(id, p);
          current.current.retained.positions[id] = p;
        }
        labelsRef.current();
      }, current.current.retained.positions, current.current.reduced, complete);
    });
    return () => { cancelAnimationFrame(frame); layout.current?.kill(); };
  }, [topology, props.snapshot.searchGeneration]);
  useEffect(() => { if (props.session.paused) layout.current?.stop(); }, [props.session.paused]);
  return <div ref={stage} className="constellation-stage"><div ref={container} className="sigma-canvas" aria-label="Interactive evidence graph" />
    <div ref={glow} className={`question-halo${props.reduced ? ' still' : ''}`} hidden><i /></div>
    <div ref={selectedGlow} className="selection-halo" hidden><i /></div>
    <div ref={labelLayer} className="graph-label-layer" role="group" aria-label="Visible graph nodes"/><div ref={tooltip} className="graph-hover-label" role="tooltip" hidden />
  </div>;
});
