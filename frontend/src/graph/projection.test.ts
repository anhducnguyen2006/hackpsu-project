import { expect,it } from 'vitest';
import { adaptEvidence } from './adapters';
import { project } from './projection';
import { graphSession, newSession } from './graphSession';
import { EXAMPLE_DATASETS } from '../demo/researchExample';
it('renders every loaded variable and relationship without arbitrary caps',()=>{
 const snapshot=adaptEvidence({datasets:[{...EXAMPLE_DATASETS[0],variables:Array.from({length:400},(_,i)=>`Column ${i}`)}],question:'Q',generation:1});
 const visible=project(snapshot,newSession());
 expect(visible.nodes).toHaveLength(snapshot.nodes.length);
 expect(visible.edges).toHaveLength(snapshot.edges.length);
 expect(visible.nodes.some(n=>n.label==='Column 399')).toBe(true);
});
it('combines checkbox selections and resets filters without discarding exploration',()=>{
 const snapshot=adaptEvidence({datasets:EXAMPLE_DATASETS,question:'Q',generation:1});
 const initial={...newSession(),selected:snapshot.nodes[0].id,camera:{x:.4,y:.6,ratio:1.2,angle:0}};
 let session=graphSession(initial,{type:'filter',key:'nodeType',value:['dataset','variable']});
 session=graphSession(session,{type:'filter',key:'evidence',value:['documented']});
 const projected=project(snapshot,session);
 expect(projected.nodes.every(n=>['dataset','variable'].includes(n.kind))).toBe(true);
 expect(projected.edges.length).toBe(6);
 expect(projected.edges.every(e=>e.evidenceClass==='documented')).toBe(true);
 session=graphSession(session,{type:'filter',key:'evidence',value:[]});
 expect(project(snapshot,session).edges).toHaveLength(0);
 session=graphSession(session,{type:'resetFilters'});
 expect(project(snapshot,session).edges).toHaveLength(snapshot.edges.length);
 expect(session.camera).toEqual(initial.camera);expect(session.selected).toBe(initial.selected);
});
it('applies only explicitly selected filters and retains complete source evidence',()=>{
 const snapshot=adaptEvidence({datasets:EXAMPLE_DATASETS,question:'Q',generation:1});
 const session={...newSession(),nodeType:['variable']};
 expect(project(snapshot,session).nodes.every(n=>n.kind==='variable')).toBe(true);
 expect(snapshot.nodes.some(n=>n.kind==='dataset')).toBe(true);
});
