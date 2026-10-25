import { CatmullRomCurve3, Vector3 } from "three";
import { arrivalCamera, type Point3 } from "./sceneModel";

const vector = (point: Point3) => new Vector3(...point);
export const smoothRange = (start: number, end: number, value: number) => {
  const t = Math.max(0, Math.min(1, (value - start) / (end - start)));
  return t * t * (3 - 2 * t);
};

/** Pure sampling: a given progress always returns the same pose, in either direction. */
export function createCameraJourney(width: number, height: number) {
  const view = arrivalCamera(width, height);
  const positions: Point3[] = view.portrait ? [
    view.position, [3.1, 0.5, 6.5], [3.2, 0.35, 2.8], [3.3, 0.2, 0],
    [3.8, 0.55, -4.8], [4.8, 0.8, -9], [7.8, 0.65, -11.5],
  ] : [
    view.position, [1.3, 0.45, 8.2], [2.6, 0.2, 4.4], [3.6, 0.25, 0],
    [4.2, 0.6, -6.8], [5.7, 0.9, -12], [11, 0.6, -14],
  ];
  const targets: Point3[] = view.portrait ? [
    view.target, [3.3, 0.1, -1], [3.5, 0.2, -3.4], [3.8, 0.3, -6],
    [4.2, 0.5, -11], [5.8, 0.7, -17], [8.6, 0.7, -21],
  ] : [
    view.target, [3, 0.1, -1], [3.8, 0.2, -3.4], [4.2, 0.3, -7.5],
    [4.8, 0.6, -14], [6.3, 0.7, -21], [11.8, 0.7, -24],
  ];
  const positionCurve = new CatmullRomCurve3(positions.map(vector), false, "centripetal");
  const targetCurve = new CatmullRomCurve3(targets.map(vector), false, "centripetal");
  return {
    sample(progress: number, position = new Vector3(), target = new Vector3()) {
      const t = Math.max(0, Math.min(1, progress));
      positionCurve.getPoint(t, position);
      targetCurve.getPoint(t, target);
      return { position, target, framing: 1 - smoothRange(0, 0.32, t), networkAlpha: smoothRange(0.2, 0.62, t) };
    },
  };
}
