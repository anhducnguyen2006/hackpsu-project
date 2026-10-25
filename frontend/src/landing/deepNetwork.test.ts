import { expect, it } from "vitest";
import { Vector3 } from "three";
import { createCameraJourney } from "./cameraJourney";
import { createDeepNetwork } from "./deepNetwork";

it.each([[1440, 900], [390, 844]])("distributes reproducible nodes across three Z layers with a clear camera corridor at %s wide", (width, height) => {
  const nodes = createDeepNetwork(width, height);
  expect(nodes).toEqual(createDeepNetwork(width, height));
  const depth = Array.from(nodes).filter((_, i) => i % 3 === 2);
  expect(depth.some(z => z > -12)).toBe(true);
  expect(depth.some(z => z < -19 && z > -23)).toBe(true);
  expect(depth.some(z => z < -30)).toBe(true);
  expect(nodes.length / 3).toBeLessThanOrEqual(width < 760 ? 72 : 126);
  const journey = createCameraJourney(width, height);
  for (let i = 0; i < nodes.length; i += 3) {
    const point = new Vector3(nodes[i], nodes[i + 1], nodes[i + 2]);
    for (let j = 0; j <= 120; j++) expect(point.distanceTo(journey.sample(j / 120).position)).toBeGreaterThan(1.39);
  }
});
