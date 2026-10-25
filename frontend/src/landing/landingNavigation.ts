import { gsap } from "gsap";
import { createNavigationDirection } from "./navigationState";

/** Called inside the landing useGSAP context; consumes the existing ScrollTrigger's updates. */
export function createLandingNavigation(root: HTMLElement) {
  const header = root.querySelector<HTMLElement>('[data-landing-header]');
  if (!header) return { update: (_position: number) => {}, dispose: () => {} };
  const direction = createNavigationDirection(window.scrollY);
  const tween = gsap.fromTo(header, { yPercent: 0 }, { yPercent: -110, duration: 0.28, ease: "power2.inOut", paused: true });
  const focus = () => {
    direction.reset(window.scrollY);
    // Keyboard navigation reveals immediately, without waiting for a scroll or a tween.
    tween.pause(0);
  };
  header.addEventListener("focusin", focus);
  return {
    update(position: number) {
      if (header.contains(document.activeElement)) { direction.reset(position); tween.pause(0); return; }
      const action = direction.update(position);
      if (action === "show") tween.reverse();
      if (action === "hide") tween.play();
    },
    dispose() { header.removeEventListener("focusin", focus); tween.kill(); },
  };
}
