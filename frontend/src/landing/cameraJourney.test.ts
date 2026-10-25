import { expect, it } from "vitest";
import { Vector3 } from "three";
import { createCameraJourney } from "./cameraJourney";
import { arrivalCamera, SPHERE_CENTER, SPHERE_RADIUS } from "./sceneModel";

it.each([[1440, 900], [390, 844]])("preserves the opening, enters and exits the actual sphere at %s wide", (width, height) => {
  const journey = createCameraJourney(width, height);
  const view = arrivalCamera(width, height);
  expect(journey.sample(0).position.toArray()).toEqual(view.position);
  expect(journey.sample(0).target.toArray()).toEqual(view.target);
  const center = new Vector3(...SPHERE_CENTER);
  const radius = SPHERE_RADIUS * view.sphereScale;
  expect(journey.sample(0).position.distanceTo(center)).toBeGreaterThan(radius);
  expect(journey.sample(0.5).position.distanceTo(center)).toBeLessThan(radius * 0.6);
  expect(journey.sample(0.8).position.z).toBeLessThan(-radius);
  expect(journey.sample(1).position.x - journey.sample(0.8).position.x).toBeGreaterThan(1);
});

it("is smooth, finite, forward-looking and deterministic in either scroll direction", () => {
  const journey = createCameraJourney(1440, 900);
  const forward = Array.from({ length: 201 }, (_, i) => journey.sample(i / 200));
  for (let i = 0; i < forward.length; i++) {
    const pose = forward[i];
    expect(pose.position.toArray().every(Number.isFinite)).toBe(true);
    expect(pose.target.z).toBeLessThan(pose.position.z);
    expect(journey.sample(i / 200).position.toArray()).toEqual(pose.position.toArray());
    if (i) expect(pose.position.distanceTo(forward[i - 1].position)).toBeLessThan(0.4);
  }
  for (let i = 200; i >= 0; i--) expect(journey.sample(i / 200).position.toArray()).toEqual(forward[i].position.toArray());
});
