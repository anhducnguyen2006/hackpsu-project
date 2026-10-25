import { expect, it } from 'vitest';
import { adaptEvidence } from './adapters';
import { EXAMPLE_DATASETS, EXAMPLE_INTERPRETATION } from '../demo/researchExample';

it('keeps exact dataset-owned variables and cached provenance', () => {
 const datasets = EXAMPLE_DATASETS.map(d => ({...d, variables:['A-B','AB']}));
 const model = adaptEvidence({datasets, question:'Question', generation:1, cached:true, interpretation:EXAMPLE_INTERPRETATION});
 expect(model.nodes.filter(n=>n.kind==='variable')).toHaveLength(4);
 expect(new Set(model.nodes.map(n=>n.id)).size).toBe(model.nodes.length);
 expect(model.nodes.every(n=>n.provenance.origin==='cached')).toBe(true);
 expect(model.edges.some(e=>e.source.startsWith('dataset:') && e.target.startsWith('dataset:'))).toBe(false);
});
it('rejects graph-only datasets and ambiguous normalized variable evidence', () => {
 const datasets=[{...EXAMPLE_DATASETS[0],variables:['A-B','AB']}];
 const model=adaptEvidence({datasets,question:'Q',generation:2,graph:{nodes:[{data:{id:'dataset:outsider',type:'DATASET',label:'Outside'}},{data:{id:'variable:ab',type:'VARIABLE',label:'ab'}}],edges:[{data:{id:'ambiguous',source:`dataset:${datasets[0].dataset_id}`,target:'variable:ab',relationship_type:'HAS_VARIABLE',verification_status:'verified_metadata',evidence:'Raw ambiguous evidence'}},{data:{id:'outside',source:`dataset:${datasets[0].dataset_id}`,target:'dataset:outsider',relationship_type:'POTENTIAL_JOIN',verification_status:'unverified_potential',evidence:'Maybe'}}]}});
 expect(model.nodes.some(n=>n.label==='Outside')).toBe(false);
 expect(model.edges.some(e=>e.id==='backend:ambiguous')).toBe(false);
 expect(model.warnings.join(' ')).toContain('ambiguous');
});
it('classifies semantic verified metadata as a metadata match and retains parallel evidence',()=>{
 const [a,b]=EXAMPLE_DATASETS;
 const edges=['one','two'].map(id=>({data:{id,source:`dataset:${a.dataset_id}`,target:`dataset:${b.dataset_id}`,relationship_type:'SEMANTICALLY_RELATED',verification_status:'verified_metadata',evidence:id}}));
 const model=adaptEvidence({datasets:EXAMPLE_DATASETS,question:'Q',generation:1,graph:{nodes:[],edges}});
 expect(model.edges.filter(e=>e.id.startsWith('backend:')).map(e=>e.evidenceClass)).toEqual(['metadata_supported','metadata_supported']);
});

it('keeps computed mappings separate from interpretation and exposes no invented publications', async()=>{
 const {EXAMPLE_ANALYSIS}=await import('../demo/researchExample');
 const model=adaptEvidence({datasets:EXAMPLE_DATASETS,question:'Q',generation:1,cached:true,interpretation:EXAMPLE_INTERPRETATION,analysis:EXAMPLE_ANALYSIS});
 expect(model.edges.some(e=>e.evidenceClass==='computed'&&e.provenance.evidenceText.includes('studytime'))).toBe(true);
 expect(model.nodes.some(n=>n.kind==='variable'&&n.label==='studytime')).toBe(true);
 expect(model.nodes.some(n=>n.id.includes('publication'))).toBe(false);
});
