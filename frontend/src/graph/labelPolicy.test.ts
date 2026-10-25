import { expect, it } from 'vitest';
import { placeLabels } from './labelPolicy';

it('places every label beside its node and keeps boundary labels inside the viewport', () => {
  const labels=placeLabels([
    {id:'right',x:295,y:190,radius:10,width:100,height:20},
    {id:'left',x:3,y:2,radius:6,width:90,height:20},
  ],300,200);
  expect(labels.size).toBe(2);
  for(const box of labels.values()) {
    expect(box.x).toBeGreaterThanOrEqual(4);expect(box.y).toBeGreaterThanOrEqual(4);
    expect(box.x+box.width).toBeLessThanOrEqual(296);expect(box.y+box.height).toBeLessThanOrEqual(196);
  }
  expect(labels.get('right')!.x+100).toBeLessThan(285);
});
it('reduces label collisions without suppressing labels or moving graph nodes', () => {
 const nodes=[{id:'a',x:80,y:80,radius:8,width:80,height:20},{id:'b',x:82,y:82,radius:8,width:80,height:20}];
 const before=structuredClone(nodes),labels=placeLabels(nodes,400,300);
 expect(labels.size).toBe(2);expect(nodes).toEqual(before);
 const a=labels.get('a')!,b=labels.get('b')!;
 expect(a.x+a.width<=b.x||b.x+b.width<=a.x||a.y+a.height<=b.y||b.y+b.height<=a.y).toBe(true);
});
it('keeps labels attached to panned-offscreen nodes instead of piling them onto the canvas edge', () => {
 const labels=placeLabels([{id:'offscreen',x:500,y:100,radius:8,width:80,height:20}],300,200);
 expect(labels.get('offscreen')!.x).toBeGreaterThan(500);
});
