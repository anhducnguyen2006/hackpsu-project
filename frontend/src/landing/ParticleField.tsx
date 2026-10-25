import { useMemo } from "react";
import { createParticleConnections, createParticlePositions } from "./sceneModel";
import { useLandingPalette } from "./palette";
import { softenNearGeometry } from "./nearFade";

export default function ParticleField({ mobile }: { mobile: boolean }) {
  const PALETTE = useLandingPalette();
  const particles = useMemo(() => createParticlePositions(mobile ? 48 : 96), [mobile]);
  const connections = useMemo(() => createParticleConnections(particles, mobile ? 10 : 24, mobile ? 4.2 : 3), [particles, mobile]);
  return <>
    <points name="scientific-particles" raycast={() => null}>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[particles, 3]} /></bufferGeometry>
      <pointsMaterial transparent depthWrite={false} color={PALETTE.aubergine} size={mobile ? 0.055 : 0.045} sizeAttenuation toneMapped={false} onBeforeCompile={softenNearGeometry} />
    </points>
    <lineSegments name="illustrative-connections" raycast={() => null}>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[connections, 3]} /></bufferGeometry>
      <lineBasicMaterial color={PALETTE.aubergine} transparent opacity={0.28} depthWrite={false} toneMapped={false} onBeforeCompile={softenNearGeometry} />
    </lineSegments>
  </>;
}
