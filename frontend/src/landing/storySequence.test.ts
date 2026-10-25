import { expect, it } from "vitest";
import { gsap } from "gsap";
import { appendStorySequence } from "./storySequence";
import { appendCollageSequence } from "./collageSequence";
import { STORY_TIMING, FLIGHT_SCALE, LANDING_DURATION } from "./storyTiming";

it("retains the camera range and starts evidence after the statement exits", () => {
  expect(360 * FLIGHT_SCALE).toBe(216);
  expect(300 * FLIGHT_SCALE).toBe(180);
  expect(STORY_TIMING.evidence).toBeGreaterThan(STORY_TIMING.statementExit);
});

it("seeks through the story and evidence section identically in both scroll directions", () => {
  const root = document.createElement("div");
  root.innerHTML = `<div data-flight-copy></div><div data-flight-annotations></div><div data-flight-world></div>
    <section data-story-panels></section><section data-story-statement><span data-statement-line>Evidence</span></section>
    <section data-evidence-scene style="opacity: 0; visibility: hidden"></section>`;
  document.body.append(root);
  const clock = { settle: 0, darkness: 0, worldVisibility: 1, statement: 0, evidence: 0 };
  const ctx = gsap.context(() => {
    const tl = gsap.timeline({ paused: true, defaults: { ease: "none" } });
    appendStorySequence(tl, clock);
    appendCollageSequence(tl, root, clock);
    expect(tl.duration()).toBeCloseTo(LANDING_DURATION);
    const nodes = [...root.querySelectorAll<HTMLElement>("[data-story-panels], [data-story-statement], [data-statement-line], [data-evidence-scene]")];
    const times = [0, .7, 1.2, 1.9, 2.15, 2.7, LANDING_DURATION];
    const snapshots = times.map(time => { tl.time(time); return nodes.map(node => node.style.cssText); });
    expect(snapshots[2][0]).toContain("opacity: 1");
    expect(snapshots[4][1]).toContain("opacity: 1");
    expect(snapshots[6][3]).toContain("opacity: 1");
    [...times].reverse().forEach(time => {
      tl.time(time);
      expect(nodes.map(node => node.style.cssText)).toEqual(snapshots[times.indexOf(time)]);
    });
  }, root);
  ctx.revert();
  root.remove();
});
