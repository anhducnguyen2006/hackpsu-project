import { render, fireEvent } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { adaptEvidence } from './adapters';
import { EXAMPLE_DATASETS } from '../demo/researchExample';
import { newSession } from './graphSession';
const { instances } = vi.hoisted(() => ({ instances: [] as { options: any; graph: any; camera: any; kill: ReturnType<typeof vi.fn>; listeners: Record<string, Function[]> }[] }));
vi.mock('sigma', () => ({ default: class {
  listeners: Record<string, Function[]> = {};
  constructor(graph: any, _host: any, options: any) { instances.push({ graph, options, camera:this.camera, kill: this.kill, listeners:this.listeners }); }
  getMouseLayer = () => document.createElement("div");
  kill = vi.fn(); on = (event:string, handler:Function) => { (this.listeners[event] ??= []).push(handler); }; refresh = vi.fn();
  camera = {
    ratio:1,
    on:(event:string, handler:Function) => { (this.listeners[`camera:${event}`] ??= []).push(handler); },
    setState:vi.fn(() => { this.listeners['camera:updated']?.forEach(handler=>handler()); }),
    getState:() => ({x:.5,y:.5,ratio:1,angle:0}),
  };
  getCamera = () => this.camera;
  scaleSize = (size: number) => size;
  graphToViewport = () => ({x:100,y:100});
} }));
vi.mock('sigma/rendering', () => ({ layerDashed: () => ({glsl:'if (dashSize < dashThreshold || gapSize < dashThreshold) {\n    return vec4(0.0);'}), layerFill: () => ({glsl:'return v_fillColor;'}) }));
import { SigmaGraph } from './SigmaGraph';
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); instances.length=0; });
it('binds both coordinates explicitly and renders every loaded node, then releases the renderer', () => {
 vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);
 vi.stubGlobal('ResizeObserver', class {observe(){} disconnect(){}});
 const snapshot=adaptEvidence({datasets:[{...EXAMPLE_DATASETS[0],variables:Array.from({length:120},(_,i)=>`Column ${i}`)}],question:'Q',generation:1});
 const session=newSession(); const failure=vi.fn();
 const screen=render(<SigmaGraph projection={snapshot} snapshot={snapshot} session={session} retained={session} onSelect={()=>{}} onFailure={failure} reduced onAnchor={()=>{}}/>);
 expect(instances[0].options.styles.nodes.x).toEqual({attribute:'x'});
 expect(instances[0].options.styles.nodes.y).toEqual({attribute:'y'});
 expect(instances[0].graph.order).toBe(snapshot.nodes.length);
 expect(instances[0].graph.size).toBe(snapshot.edges.length);
 for(const id of instances[0].graph.edges()){expect(instances[0].graph.hasNode(instances[0].graph.source(id))).toBe(true);expect(instances[0].graph.hasNode(instances[0].graph.target(id))).toBe(true);}
 expect(instances[0].options.primitives.edges.layers[0].glsl).toContain('return dashColor;');
 expect(instances[0].options.primitives.edges.layers[0].glsl).not.toContain('return vec4(0.0);');
 expect(instances[0].options.settings.itemSizesReference).toBe('screen');
 expect(instances[0].options.primitives.edges.variables.gap).toEqual({type:'number',default:0});
 expect(failure).not.toHaveBeenCalled();
 screen.unmount();expect(instances[0].kill).toHaveBeenCalledOnce();
});
it('keeps every node label visible at every zoom without duplicate node tooltips', () => {
 vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);
 vi.stubGlobal('ResizeObserver', class {observe(){} disconnect(){}});
 const snapshot=adaptEvidence({datasets:EXAMPLE_DATASETS,question:'Q',generation:1});
 const session=newSession();
 const view=render(<SigmaGraph projection={snapshot} snapshot={snapshot} session={session} retained={session} onSelect={()=>{}} onFailure={()=>{}} reduced onAnchor={()=>{}}/>);
 const instance=instances[0];
 for (const ratio of [.05,1,15]) {
   instance.camera.ratio=ratio;
   instance.listeners['camera:updated'].forEach(handler=>handler());
   expect(view.getAllByRole('button',{name:/^Inspect /})).toHaveLength(snapshot.nodes.length);
 }
 instance.listeners.enterNode.forEach(handler=>handler({node:'dataset:uci:320'}));
 expect(view.queryByRole('tooltip')).not.toBeInTheDocument();
 expect(view.getByRole('button',{name:'Inspect Student Performance'})).not.toHaveAttribute('title');
 expect(view.getAllByRole('button',{name:/^Inspect /})).toHaveLength(snapshot.nodes.length);
});
it('restores the camera before graph population without reading absent node coordinates', () => {
 vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);
 vi.stubGlobal('ResizeObserver', class {observe(){} disconnect(){}});
 const snapshot=adaptEvidence({datasets:EXAMPLE_DATASETS,question:'Q',generation:1});
 const session={...newSession(),camera:{x:.4,y:.6,ratio:1,angle:0}}, failure=vi.fn();
 const warning=vi.spyOn(console,'warn').mockImplementation(()=>{});
 render(<SigmaGraph projection={snapshot} snapshot={snapshot} session={session} retained={session} onSelect={()=>{}} onFailure={failure} reduced onAnchor={()=>{}}/>);
 expect(failure).not.toHaveBeenCalled();expect(warning).not.toHaveBeenCalled();
 expect(instances[0].graph.order).toBe(snapshot.nodes.length);
});
it('extends node interactions to rendered labels and highlights hovered edge endpoints', () => {
 vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue(null);
 vi.stubGlobal('ResizeObserver', class {observe(){} disconnect(){}});
 const snapshot=adaptEvidence({datasets:EXAMPLE_DATASETS,question:'Q',generation:1});
 const session=newSession(), select=vi.fn();
 const view=render(<SigmaGraph projection={snapshot} snapshot={snapshot} session={session} retained={session} onSelect={select} onFailure={()=>{}} reduced onAnchor={()=>{}}/>);
 const instance=instances[0];
 expect(instance.options.settings.nodeLabelEvents).toBe('extend');
 const label=view.getByRole('button',{name:'Inspect Q'});
 fireEvent.focus(label);
 expect(instance.graph.getNodeAttribute('variable:uci:320:studytime','opacity')).toBe(.2);
 fireEvent.click(label);expect(select).toHaveBeenCalledWith('question:1');
 fireEvent.blur(label);
 expect(instance.graph.getNodeAttribute('variable:uci:320:studytime','opacity')).toBe(1);
 const edge=snapshot.edges.find(e=>e.relationship==='Documented variable')!;
 instance.listeners.enterEdge.forEach(handler=>handler({edge:edge.id}));
 expect(instance.graph.getEdgeAttribute(edge.id,'opacity')).toBe(.85);
 expect(instance.graph.getNodeAttribute(edge.source,'opacity')).toBe(1);
 expect(view.getByRole('tooltip')).toHaveTextContent('Documented variable');
 instance.listeners.clickEdge.forEach(handler=>handler({edge:edge.id}));
 expect(select).toHaveBeenLastCalledWith(edge.id);
 instance.listeners.leaveEdge.forEach(handler=>handler({edge:edge.id}));
 expect(instance.graph.getEdgeAttribute(edge.id,'opacity')).toBe(.48);
});
