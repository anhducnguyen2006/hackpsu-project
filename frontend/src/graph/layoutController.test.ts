import { afterEach, expect, it, vi } from 'vitest';
import { adaptEvidence } from './adapters';
import { EXAMPLE_DATASETS } from '../demo/researchExample';
const { workers }=vi.hoisted(()=>({workers:[] as any[]}));
vi.mock('graphology-layout-forceatlas2/worker',()=>({default:class {graph:any;options:any;start=vi.fn();stop=vi.fn();kill=vi.fn();constructor(graph:any,options:any){this.graph=graph;this.options=options;workers.push(this);}}}));
import { settleLayout } from './layoutController';
afterEach(()=>{workers.length=0;vi.useRealTimers();vi.unstubAllGlobals();});
it('settles offscreen, publishes once, uses collision-aware forces, and releases its worker',()=>{
 vi.useFakeTimers();vi.stubGlobal('Worker',class{});
 const snapshot=adaptEvidence({datasets:EXAMPLE_DATASETS,question:'Q',generation:1});
 const apply=vi.fn(),complete=vi.fn();const layout=settleLayout(snapshot,apply,{},false,complete);
 workers[0].graph.emit('eachNodeAttributesUpdated',{});
 expect(apply).not.toHaveBeenCalled();
 expect(workers[0].options.settings.adjustSizes).toBe(true);
 vi.advanceTimersByTime(1200);
 expect(apply).toHaveBeenCalledOnce();expect(complete).toHaveBeenCalledOnce();expect(workers[0].kill).toHaveBeenCalledOnce();
 layout.kill();expect(workers[0].kill).toHaveBeenCalledOnce();
});
