import { Vector3 } from "three";
import { createCameraJourney } from "./cameraJourney";

export function createDeepNetwork(width: number, height: number) {
  const mobile = width < 760;
  const journey = createCameraJourney(width, height);
  const corridor = Array.from({ length: 121 }, (_, i) => journey.sample(i / 120).position);
  const positions: number[] = [];
  const point = new Vector3();
  const count = mobile ? 24 : 42;
  for (let layer = 0; layer < 3; layer++) {
    for (let i = 0; i < count; i++) {
      const angle = i * Math.PI * (3 - Math.sqrt(5)) + layer * 0.7;
      const radius = 1.8 + ((i * 17) % 31) / 31 * (6 + layer * 2);
      point.set(3 + layer * 2 + Math.cos(angle) * radius, Math.sin(angle) * radius * 0.7, -10 - layer * 11 + Math.sin(i * 2.1) * 1.8);
      if (corridor.every((camera) => camera.distanceToSquared(point) > 1.4 * 1.4)) positions.push(point.x, point.y, point.z);
    }
  }
  return new Float32Array(positions);
}
