export type Point3 = [number, number, number];

export const SPHERE_RADIUS = 5.8;
export const SPHERE_CENTER: Point3 = [3, 0, 0];
export const SPHERE_ROTATION: Point3 = [0.32, -0.2, -0.3];
export const ANNULUS_ROTATION: Point3 = [1.12, 0.18, -0.3];
export const ANNULUS_CENTER: Point3 = [3, -0.3, 0];
export const ANNULUS_INNER = 6.2;
export const ANNULUS_OUTER = 7.05;

export function createSphereLines(meridians: number, parallels: number) {
  const positions: number[] = [];
  function addCurve(point: (t: number) => Point3, steps: number) {
    for (let i = 0; i < steps; i++) positions.push(...point(i / steps), ...point((i + 1) / steps));
  }
  const r = SPHERE_RADIUS;
  for (let i = 0; i < meridians; i++) {
    const angle = i * Math.PI * 2 / meridians;
    addCurve((t) => [r * Math.sin(t * Math.PI) * Math.cos(angle), r * Math.cos(t * Math.PI), r * Math.sin(t * Math.PI) * Math.sin(angle)], 80);
  }
  for (let i = 1; i <= parallels; i++) {
    const angle = i * Math.PI / (parallels + 1);
    addCurve((t) => [r * Math.sin(angle) * Math.cos(t * Math.PI * 2), r * Math.cos(angle), r * Math.sin(angle) * Math.sin(t * Math.PI * 2)], 128);
  }
  return new Float32Array(positions);
}

export function createParticlePositions(count: number) {
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const y = 1 - 2 * (i + 0.5) / count;
    const radial = Math.sqrt(1 - y * y);
    const angle = i * Math.PI * (3 - Math.sqrt(5));
    const radius = SPHERE_RADIUS * (0.93 + ((i * 37) % 23) / 90);
    positions.set([Math.cos(angle) * radial * radius, y * radius, Math.sin(angle) * radial * radius], i * 3);
  }
  return positions;
}

export function arrivalCamera(width: number, height: number) {
  const portrait = width < 760;
  // Preserve the approved upper mobile composition while the canvas fills the viewport.
  const framingHeight = portrait ? Math.min(height, 780) : height;
  return {
    position: (portrait ? [3, 0.8, 12.5] : [0, 0.6, 13]) as Point3,
    target: (portrait ? [3, -1.3, 0] : [1.2, 0, 0]) as Point3,
    fov: portrait ? 2 * Math.atan(Math.tan(26 * Math.PI / 180) * height / framingHeight) * 180 / Math.PI : 38,
    offsetX: width * (portrait ? -0.22 : -0.25),
    offsetY: portrait ? framingHeight * 0.12 + (height - framingHeight) / 2 : height * 0.03,
    sphereScale: portrait ? 0.65 : 1,
    annulusScale: portrait ? 0.68 : 1,
    annulusRotation: (portrait ? [0.75, 0.18, -0.55] : ANNULUS_ROTATION) as Point3,
    portrait,
  };
}

export function transformPoint(point: Point3, rotation: Point3, center: Point3): Point3 {
  const [rx, ry, rz] = rotation;
  const [x, y, z] = point;
  const x1 = x * Math.cos(rz) - y * Math.sin(rz);
  const y1 = x * Math.sin(rz) + y * Math.cos(rz);
  const x2 = x1 * Math.cos(ry) + z * Math.sin(ry);
  const z2 = -x1 * Math.sin(ry) + z * Math.cos(ry);
  return [x2 + center[0], y1 * Math.cos(rx) - z2 * Math.sin(rx) + center[1], y1 * Math.sin(rx) + z2 * Math.cos(rx) + center[2]];
}

function normalize([x, y, z]: Point3): Point3 {
  const length = Math.hypot(x, y, z);
  return [x / length, y / length, z / length];
}

export function createProjector(width: number, height: number) {
  const view = arrivalCamera(width, height);
  const forward = normalize(view.target.map((v, i) => v - view.position[i]) as Point3);
  const right = normalize([-forward[2], 0, forward[0]]);
  const up: Point3 = [right[1] * forward[2] - right[2] * forward[1], right[2] * forward[0] - right[0] * forward[2], right[0] * forward[1] - right[1] * forward[0]];
  const focal = height / (2 * Math.tan(view.fov * Math.PI / 360));
  return (point: Point3) => {
    const delta = point.map((value, i) => value - view.position[i]);
    const dot = (axis: Point3) => delta.reduce((sum, value, i) => sum + value * axis[i], 0);
    const depth = dot(forward);
    return [width / 2 + dot(right) * focal / depth - view.offsetX, height / 2 - dot(up) * focal / depth - view.offsetY];
  };
}

/** Sparse, deterministic local links; never imply verified scientific relationships. */
export function createParticleConnections(particles: Float32Array, limit: number, maxDistance: number) {
  const edges: { a: number; b: number; distance: number }[] = [];
  for (let a = 0; a < particles.length; a += 3) {
    for (let b = a + 3; b < particles.length; b += 3) {
      const distance = Math.hypot(particles[a] - particles[b], particles[a + 1] - particles[b + 1], particles[a + 2] - particles[b + 2]);
      if (distance <= maxDistance) edges.push({ a, b, distance });
    }
  }
  edges.sort((a, b) => a.distance - b.distance);
  const result: number[] = [];
  const degree = new Map<number, number>();
  for (const { a, b } of edges) {
    if (result.length >= limit * 6) break;
    if ((degree.get(a) ?? 0) >= 2 || (degree.get(b) ?? 0) >= 2) continue;
    result.push(...particles.slice(a, a + 3), ...particles.slice(b, b + 3));
    degree.set(a, (degree.get(a) ?? 0) + 1);
    degree.set(b, (degree.get(b) ?? 0) + 1);
  }
  return new Float32Array(result);
}
