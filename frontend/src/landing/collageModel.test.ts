import { expect, it } from "vitest";
import { exitDisplacement } from "./collageModel";

it("retains the sphere camera handoff without a jump in position or velocity", () => {
  const delta = 0.0001;
  expect(exitDisplacement(0)).toBe(0);
  expect((exitDisplacement(delta) - exitDisplacement(0)) / delta).toBeCloseTo(0.28, 3);
  expect((exitDisplacement(1) - exitDisplacement(1 - delta)) / delta).toBeLessThan(0.0001);
  expect(exitDisplacement(1)).toBeGreaterThan(0);
});
