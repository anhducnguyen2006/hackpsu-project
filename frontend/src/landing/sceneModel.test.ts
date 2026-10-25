import { expect, it } from "vitest";
import { createParticleConnections, createParticlePositions, createProjector, createSphereLines, SPHERE_RADIUS, transformPoint } from "./sceneModel";

it("matches the renderer's XYZ Euler rotation in the reduced-motion projection", () => {
  const transformed = transformPoint([0, 0, 1], [Math.PI / 2, Math.PI / 2, 0], [0, 0, 0]);
  expect(transformed[0]).toBeCloseTo(1);
  expect(transformed[1]).toBeCloseTo(0);
  expect(transformed[2]).toBeCloseTo(0);
});

it("places every wireframe vertex on the same sphere, with finite segment endpoints", () => {
  const vertices = createSphereLines(24, 16);
  expect(vertices.length % 6).toBe(0);
  expect(vertices.length).toBeGreaterThan(1000);
  for (let i = 0; i < vertices.length; i += 3) {
    expect(Math.hypot(vertices[i], vertices[i + 1], vertices[i + 2])).toBeCloseTo(SPHERE_RADIUS, 4);
  }
});

it("keeps sparse particles reproducible across remounts and distributed around the sphere", () => {
  const positions = createParticlePositions(96);
  expect(positions).toEqual(createParticlePositions(96));
  expect(positions.length).toBe(96 * 3);
  for (let axis = 0; axis < 3; axis++) {
    const values = Array.from(positions).filter((_, index) => index % 3 === axis);
    expect(Math.min(...values)).toBeLessThan(-SPHERE_RADIUS * 0.7);
    expect(Math.max(...values)).toBeGreaterThan(SPHERE_RADIUS * 0.7);
  }
});

it("connects only existing particles with a bounded number of short spatial edges", () => {
  const particles = createParticlePositions(96);
  const connections = createParticleConnections(particles, 20, 3);
  const points = new Set(Array.from({ length: particles.length / 3 }, (_, i) => Array.from(particles.slice(i * 3, i * 3 + 3)).join(",")));
  expect(connections.length).toBeGreaterThan(0);
  expect(connections.length).toBeLessThanOrEqual(20 * 6);
  let depthEdges = 0;
  for (let i = 0; i < connections.length; i += 6) {
    const a = Array.from(connections.slice(i, i + 3));
    const b = Array.from(connections.slice(i + 3, i + 6));
    expect(points.has(a.join(","))).toBe(true);
    expect(points.has(b.join(","))).toBe(true);
    expect(Math.hypot(...a.map((n, axis) => n - b[axis]))).toBeLessThanOrEqual(3);
    if (Math.abs(a[2] - b[2]) > 0.2) depthEdges++;
  }
  expect(depthEdges).toBeGreaterThan(0);
  expect(connections).toEqual(createParticleConnections(particles, 20, 3));
});


it("preserves the mobile scientific framing when the full-height canvas extends below the reading field", () => {
  const previous = createProjector(390, 780)([3, 0, 0]);
  const fullViewport = createProjector(390, 844)([3, 0, 0]);
  expect(fullViewport[0]).toBeCloseTo(previous[0]);
  expect(fullViewport[1]).toBeCloseTo(previous[1]);
});
