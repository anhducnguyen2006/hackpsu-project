import { useMemo } from "react";
import { useLandingPalette } from "./palette";
import { softenNearGeometry } from "./nearFade";

export default function ScientificFrames() {
  const PALETTE = useLandingPalette();
  const references = useMemo(() => new Float32Array([
    -8.5, 0, -2, 8.5, 0, -2,
    0, -7.5, -2, 0, 7.5, -2,
    -0.12, -7, -2, 0.12, -7, -2,
    -0.12, 7, -2, 0.12, 7, -2,
    -8, -0.12, -2, -8, 0.12, -2,
    8, -0.12, -2, 8, 0.12, -2,
    // Foreground calibration bracket, separated from the rear reference plane.
    3.8, -3, 2.5, 4.8, -3, 2.5,
    4.8, -3, 2.5, 4.8, -2.4, 2.5,
    4.3, -3.08, 2.5, 4.3, -2.92, 2.5,
  ]), []);
  return <lineSegments name="scientific-frames" raycast={() => null}>
    <bufferGeometry><bufferAttribute attach="attributes-position" args={[references, 3]} /></bufferGeometry>
    <lineBasicMaterial color={PALETTE.aubergine} transparent opacity={0.25} depthWrite={false} toneMapped={false} onBeforeCompile={softenNearGeometry} />
  </lineSegments>;
}
