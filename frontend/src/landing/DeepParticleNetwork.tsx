import { useThree } from "@react-three/fiber";
import { useMemo } from "react";
import { createDeepNetwork } from "./deepNetwork";
import { createParticleConnections } from "./sceneModel";
import { PALETTE } from "./palette";
import { softenNearGeometry } from "./nearFade";
import type { WorldHandles } from "./worldHandles";

export default function DeepParticleNetwork({ handles }: { handles: WorldHandles }) {
  const { size } = useThree();
  const mobile = size.width < 760;
  const positions = useMemo(() => createDeepNetwork(size.width, size.height), [size.width, size.height]);
  const connections = useMemo(() => createParticleConnections(positions, mobile ? 48 : 84, 4.8), [positions, mobile]);
  return <group name="deep-particle-network">
    <points name="depth-particles" raycast={() => null}>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[positions, 3]} /></bufferGeometry>
      <pointsMaterial ref={handles.networkPoints} color={PALETTE.aubergine} size={0.075} transparent opacity={0} depthWrite={false} sizeAttenuation toneMapped={false} onBeforeCompile={softenNearGeometry} />
    </points>
    <lineSegments name="depth-connections" raycast={() => null}>
      <bufferGeometry><bufferAttribute attach="attributes-position" args={[connections, 3]} /></bufferGeometry>
      <lineBasicMaterial ref={handles.networkLines} color={PALETTE.aubergine} transparent opacity={0} depthWrite={false} toneMapped={false} onBeforeCompile={softenNearGeometry} />
    </lineSegments>
  </group>;
}
