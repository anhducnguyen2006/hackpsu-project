import { gsap } from "gsap";
import { FLIGHT_SCALE as F, STORY_TIMING, LANDING_DURATION } from "./storyTiming";

export type CollageClock = { settle: number; worldVisibility: number; darkness: number; evidence: number };

/** The existing master calls this handoff. Only the outer section is animated;
 * DriftWall owns every internal transform and animation frame. */
export function appendCollageSequence(timeline: gsap.core.Timeline, root: HTMLElement, clock: CollageClock) {
  const scene = root.querySelector<HTMLElement>('[data-evidence-scene]');
  if (!scene) return;
  timeline.to(clock, { settle: 1, duration: 0.28 * F }, F)
    .to('[data-flight-copy], [data-flight-annotations]', { autoAlpha: 0, duration: 0.18 * F }, 1.02 * F)
    .to(clock, { darkness: 1, duration: 0.28 * F }, 1.12 * F)
    .to('[data-flight-world]', { autoAlpha: 0, duration: 0.34 * F }, 1.16 * F)
    .to(clock, { worldVisibility: 0, duration: 0.34 * F }, 1.16 * F)
    .fromTo(scene, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.26 }, STORY_TIMING.evidence)
    .to(clock, { evidence: 1, duration: 0.3 }, STORY_TIMING.evidence)
    .to({}, { duration: 0.1 }, LANDING_DURATION - 0.1);
}
