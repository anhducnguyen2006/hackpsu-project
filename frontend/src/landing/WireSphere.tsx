import { useMemo } from "react";
import { createSphereLines } from "./sceneModel";
import { PALETTE } from "./palette";
import { softenNearGeometry } from "./nearFade";

export default function WireSphere({ mobile }: { mobile: boolean }) {
  const wire = useMemo(() => createSphereLines(mobile ? 16 : 24, mobile ? 10 : 16), [mobile]);
  return <lineSegments name="wireframe-sphere" raycast={() => null}>
    <bufferGeometry><bufferAttribute attach="attributes-position" args={[wire, 3]} /></bufferGeometry>
    <lineBasicMaterial color={PALETTE.aubergine} transparent opacity={0.68} depthWrite={false} toneMapped={false} onBeforeCompile={softenNearGeometry} />
  </lineSegments>;
}
