import { useRef } from "react";
import { useThree } from "@react-three/fiber";
import { ANNULUS_CENTER, arrivalCamera, SPHERE_CENTER, SPHERE_ROTATION } from "./sceneModel";
import { LandingPaletteContext, useAnimatedLandingPalette } from "./palette";
import type { WorldHandles } from "./worldHandles";
import WireSphere from "./WireSphere";
import ParticleField from "./ParticleField";
import ScientificFrames from "./ScientificFrames";
import SpatialAnnulus from "./SpatialAnnulus";
import DeepParticleNetwork from "./DeepParticleNetwork";

export default function ResearchWorld({ handles }: { handles: WorldHandles }) {
  const PALETTE = useAnimatedLandingPalette();
  const fogArgs = useRef<[string, number, number]>([PALETTE.ice, 9, 25]);
  const { size } = useThree();
  const view = arrivalCamera(size.width, size.height);

  return <LandingPaletteContext.Provider value={PALETTE}>
    <fog attach="fog" args={fogArgs.current} color={PALETTE.ice} />
    <group ref={handles.world} name="research-world">
      <group ref={handles.annulus} name="annulus-rig" position={ANNULUS_CENTER} rotation={view.annulusRotation} scale={view.annulusScale}>
        <group ref={handles.annulusAmbient} name="annulus-ambient"><SpatialAnnulus mobile={view.portrait} /></group>
      </group>
      <group ref={handles.sphere} name="sphere-rig" position={SPHERE_CENTER} rotation={SPHERE_ROTATION} scale={view.sphereScale}>
        <group ref={handles.sphereAmbient} name="sphere-ambient">
          <WireSphere mobile={view.portrait} />
          <group ref={handles.particles} name="particle-rig"><ParticleField mobile={view.portrait} /></group>
        </group>
        <group ref={handles.frames} name="frame-rig"><ScientificFrames /></group>
      </group>
      <DeepParticleNetwork handles={handles} />
    </group>
  </LandingPaletteContext.Provider>;
}
