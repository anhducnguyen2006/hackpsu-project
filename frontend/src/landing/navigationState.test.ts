import { expect, it } from "vitest";
import { createNavigationDirection, chromeInk } from "./navigationState";

it("requires sustained movement before hiding or changing direction", () => {
  const direction = createNavigationDirection(0);
  expect(direction.update(5)).toBeNull();
  expect(direction.update(10)).toBeNull();
  expect(direction.update(16)).toBe("hide");
  expect(direction.update(15)).toBeNull();
  expect(direction.update(16)).toBeNull();
  expect(direction.update(14)).toBeNull();
  expect(direction.update(7)).toBeNull();
  expect(direction.update(2)).toBe("show");
});

it("reveals at the top regardless of previous direction and filters tiny reversals", () => {
  const direction = createNavigationDirection(300);
  expect(direction.update(330)).toBe("hide");
  expect(direction.update(327)).toBeNull();
  expect(direction.update(320)).toBeNull();
  expect(direction.update(315)).toBe("show");
  expect(direction.update(318)).toBeNull();
  expect(direction.update(316)).toBeNull();
  expect(direction.update(0)).toBe("show");
});

it("chooses contrasting palette inks for the light and dark scenes", () => {
  expect(chromeInk(0)).toBe("#3A0F34");
  expect(chromeInk(1)).toBe("#F6F7F6");
});
