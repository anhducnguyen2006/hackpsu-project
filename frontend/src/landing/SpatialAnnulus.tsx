import { useMemo } from "react";
import { DoubleSide, Path, Shape } from "three";
import { ANNULUS_INNER, ANNULUS_OUTER } from "./sceneModel";
import { PALETTE } from "./palette";

export default function SpatialAnnulus({ mobile }: { mobile: boolean }) {
  const shape = useMemo(() => {
    const disc = new Shape();
    disc.absarc(0, 0, ANNULUS_OUTER, 0, Math.PI * 2, false);
    const hole = new Path();
    hole.absarc(0, 0, ANNULUS_INNER, 0, Math.PI * 2, true);
    disc.holes.push(hole);
    return disc;
  }, []);
  return <mesh name="marigold-annulus" position={[0, 0, -0.06]} raycast={() => null}>
    <extrudeGeometry args={[shape, { depth: 0.12, bevelEnabled: false, steps: 1, curveSegments: mobile ? 64 : 96 }]} />
    <meshBasicMaterial color={PALETTE.marigold} side={DoubleSide} fog={false} toneMapped={false} />
  </mesh>;
}
