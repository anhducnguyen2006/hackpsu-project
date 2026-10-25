export interface LabelAnchor { id: string; x: number; y: number; radius: number; width: number; height: number }
interface LabelBox { x: number; y: number; width: number; height: number }
const overlap = (a: LabelBox, b: LabelBox) => Math.max(0, Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)) *
  Math.max(0, Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y));

/** Place every label without changing graph coordinates or hiding crowded labels. */
export function placeLabels(nodes: LabelAnchor[], width: number, height: number) {
  const result = new Map<string, LabelBox>();
  const nodeBoxes = nodes.map(n => ({x:n.x-n.radius-2,y:n.y-n.radius-2,width:n.radius*2+4,height:n.radius*2+4}));
  const padding = 8, gap = 8;
  const clamp = (value: number, size: number, limit: number) => limit > 0 ? Math.max(padding, Math.min(limit-padding-size,value)) : value;
  for (const node of nodes) {
    if ((width > 0 && (node.x+node.radius < 0 || node.x-node.radius > width)) ||
      (height > 0 && (node.y+node.radius < 0 || node.y-node.radius > height))) {
      result.set(node.id,{x:node.x+node.radius+gap,y:node.y-node.height/2,width:node.width,height:node.height});
      continue;
    }
    const labelWidth = width > 0 ? Math.min(node.width,Math.max(1,width-padding*2)) : node.width;
    const right = node.x+node.radius+gap, left = node.x-node.radius-gap-labelWidth;
    const sides = width > 0 && right+labelWidth > width-padding ? [left,right] : [right,left];
    let best: LabelBox | undefined, bestScore = Infinity;
    for (const x of sides) {
      for (const offset of [0,-22,22,-44,44]) {
        const box = {x:clamp(x,labelWidth,width),y:clamp(node.y-node.height/2+offset,node.height,height),width:labelWidth,height:node.height};
        let score = Math.abs(offset)*.1 + (x===sides[0] ? 0 : 1);
        for (const other of result.values()) score += overlap(box,other);
        for (const other of nodeBoxes) score += overlap(box,other)*2;
        if (score < bestScore) { best=box;bestScore=score; }
        if (score === 0) break;
      }
      if (bestScore === 0) break;
    }
    result.set(node.id,best!);
  }
  return result;
}
