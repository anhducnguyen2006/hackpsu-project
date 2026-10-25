import { gsap } from "gsap";
import { STORY_TIMING as T } from "./storyTiming";

/** Shares the camera's reversible clock, with no extra pins or triggers. */
export function appendStorySequence(timeline: gsap.core.Timeline, clock: { statement: number }) {
  gsap.set('[data-statement-line]', { yPercent: 110 });
  timeline.fromTo('[data-story-panels]', { autoAlpha: 0, yPercent: 12 }, { autoAlpha: 1, yPercent: 0, duration: .22 }, T.panels)
    .to('[data-story-panels]', { autoAlpha: 0, yPercent: -8, duration: .22 }, T.panelsExit)
    .fromTo('[data-story-statement]', { autoAlpha: 0, yPercent: 100 }, { autoAlpha: 1, yPercent: 0, duration: .26 }, T.statement)
    .to('[data-statement-line]', { yPercent: 0, duration: .18, stagger: .055 }, T.headline)
    .to(clock, { statement: 1, duration: .26 }, T.statement)
    .to('[data-story-statement]', { autoAlpha: 0, yPercent: -12, duration: .22 }, T.statementExit)
    .to(clock, { statement: 0, duration: .22 }, T.statementExit);
}
