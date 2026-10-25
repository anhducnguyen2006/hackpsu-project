/** Camera handoff retained for ScrollCameraRig; the former collage model is removed.
 * Integral of (1-u)^2 preserves exit velocity and settles continuously to rest. */
export function exitDisplacement(progress: number) {
  const u = Math.max(0, Math.min(1, progress));
  return 0.28 * (u - u * u + u * u * u / 3);
}
