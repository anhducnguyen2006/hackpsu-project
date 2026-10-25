import { useThree } from "@react-three/fiber";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useMemo, type RefObject } from "react";
import { PerspectiveCamera, Vector3 } from "three";
import { createCameraJourney } from "./cameraJourney";
import { arrivalCamera } from "./sceneModel";
import { appendCollageSequence } from "./collageSequence";
import { FLIGHT_SCALE as F } from "./storyTiming";
import { appendStorySequence } from "./storySequence";
import { exitDisplacement } from "./collageModel";
import { createLandingNavigation } from "./landingNavigation";
import { chromeInk } from "./navigationState";
import { PALETTE } from "./palette";
import type { WorldHandles } from "./worldHandles";

gsap.registerPlugin(ScrollTrigger, useGSAP);

export default function ScrollCameraRig({ handles, root }: { handles: WorldHandles; root: RefObject<HTMLDivElement> }) {
  const { camera, size, invalidate } = useThree();
  const journey = useMemo(() => createCameraJourney(size.width, size.height), [size.width, size.height]);
  useGSAP(() => {
    const element = root.current;
    if (!element || !(camera instanceof PerspectiveCamera)) return;
    const view = arrivalCamera(size.width, size.height);
    const state = { progress: 0, settle: 0, worldVisibility: 1, darkness: 0, statement: 0 };
    const navigation = createLandingNavigation(element);
    const originalInk = element.style.getPropertyValue("--landing-chrome-ink");
    let previousInk = "";
    const exit = journey.sample(1);
    const beforeExit = journey.sample(0.999);
    const exitVelocity = exit.position.clone().sub(beforeExit.position).multiplyScalar(1000);
    const targetVelocity = exit.target.clone().sub(beforeExit.target).multiplyScalar(1000);
    const position = new Vector3();
    const target = new Vector3();
    const apply = () => {
      const ink = state.statement > 0.5 ? PALETTE.aubergine : chromeInk(state.darkness);
      if (ink !== previousInk) { element.style.setProperty("--landing-chrome-ink", ink); previousInk = ink; }
      const pose = journey.sample(state.progress, position, target);
      if (state.settle > 0) {
        pose.position.addScaledVector(exitVelocity, exitDisplacement(state.settle));
        pose.target.addScaledVector(targetVelocity, exitDisplacement(state.settle));
      }
      handles.progress.current = state.progress;
      camera.position.copy(pose.position);
      camera.lookAt(pose.target);
      camera.setViewOffset(size.width, size.height, view.offsetX * pose.framing, view.offsetY * pose.framing, size.width, size.height);
      camera.updateProjectionMatrix();
      if (handles.sphereAmbient.current) {
        handles.sphereAmbient.current.rotation.set(Math.sin(state.progress * 2) * 0.025, state.progress * 0.18, 0);
      }
      if (handles.annulusAmbient.current) handles.annulusAmbient.current.rotation.set(0, Math.sin(state.progress) * 0.035, Math.sin(state.progress) * 0.016);
      if (handles.networkPoints.current) handles.networkPoints.current.opacity = pose.networkAlpha;
      if (handles.networkLines.current) handles.networkLines.current.opacity = pose.networkAlpha * 0.4;
      if (state.worldVisibility > 0) invalidate();
    };
    // A single top-level trigger owns camera progress and every overlay tween.
    const timeline = gsap.timeline({
      defaults: { ease: "none" },
      onUpdate: apply,
      scrollTrigger: {
        id: "dataopedia-flight", trigger: element, start: "top top", end: "bottom bottom",
        scrub: 0.45, invalidateOnRefresh: true,
        onUpdate: self => navigation.update(self.scroll()),
      },
    });
    timeline.to(state, { progress: 1, duration: F }, 0)
      .to('[data-flight-headline]', { autoAlpha: 0, y: -28, duration: 0.18 * F }, 0.1 * F)
      .to('[data-flight-support]', { autoAlpha: 0, y: -12, duration: 0.14 * F }, 0.16 * F)
      .to(element, { "--landing-reading-opacity": "0%", duration: 0.16 * F }, 0.14 * F)
      .fromTo('[data-flight-reveal]', { autoAlpha: 0, y: 24 }, { autoAlpha: 1, y: 0, duration: 0.18 * F }, 0.74 * F)
      .to(element, { "--landing-reading-opacity": "100%", duration: 0.16 * F }, 0.74 * F);
    appendStorySequence(timeline, state);
    appendCollageSequence(timeline, element, state);
    apply();
    // The trigger is created only once WebGL is ready and the native runway is in layout.
    timeline.scrollTrigger?.refresh();
    timeline.progress(timeline.scrollTrigger?.progress ?? 0);
    apply();
    return () => {
      navigation.dispose();
      if (originalInk) element.style.setProperty("--landing-chrome-ink", originalInk);
      else element.style.removeProperty("--landing-chrome-ink");
      handles.progress.current = 0;
    };
  }, { scope: root, dependencies: [camera, journey, size.width, size.height, handles], revertOnUpdate: true });
  return null;
}
