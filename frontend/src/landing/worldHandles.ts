import type { Group, LineBasicMaterial, PerspectiveCamera, PointsMaterial } from "three";

/** Timeline targets are separate from the inner ambient rigs, so future GSAP can own these transforms. */
export type WorldHandles = ReturnType<typeof createWorldHandles>;
export function createWorldHandles() {
  return {
    progress: { current: 0 },
    sphereAmbient: { current: null as Group | null },
    annulusAmbient: { current: null as Group | null },
    networkPoints: { current: null as PointsMaterial | null },
    networkLines: { current: null as LineBasicMaterial | null },
    camera: { current: null as PerspectiveCamera | null },
    world: { current: null as Group | null },
    sphere: { current: null as Group | null },
    particles: { current: null as Group | null },
    annulus: { current: null as Group | null },
    frames: { current: null as Group | null },
  };
}
