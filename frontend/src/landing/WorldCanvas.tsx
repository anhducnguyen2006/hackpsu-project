import { Canvas, useThree } from "@react-three/fiber";
import { useEffect, useLayoutEffect, useMemo, type RefObject } from "react";
import { NoToneMapping, PerspectiveCamera, SRGBColorSpace } from "three";
import { arrivalCamera } from "./sceneModel";
import ResearchWorld from "./ResearchWorld";
import ScrollCameraRig from "./ScrollCameraRig";
import { createWorldHandles, type WorldHandles } from "./worldHandles";

export type WorldProps = { onReady: () => void; onUnavailable: () => void; root: RefObject<HTMLDivElement>; journeyReady: boolean };

function CameraRig({ handles }: { handles: WorldHandles }) {
  const { camera, size, invalidate, setDpr } = useThree();
  useLayoutEffect(() => {
    if (!(camera instanceof PerspectiveCamera)) return;
    const view = arrivalCamera(size.width, size.height);
    handles.camera.current = camera;
    camera.position.set(...view.position);
    camera.lookAt(...view.target);
    camera.fov = view.fov;
    camera.setViewOffset(size.width, size.height, view.offsetX, view.offsetY, size.width, size.height);
    camera.updateProjectionMatrix();
    setDpr(Math.min(window.devicePixelRatio || 1, view.portrait ? 1 : 1.5));
    invalidate();
    return () => { handles.camera.current = null; };
  }, [camera, size.width, size.height, invalidate, setDpr, handles]);
  return null;
}

function WorldLifecycle({ onReady, onUnavailable }: WorldProps) {
  const { gl } = useThree();
  useEffect(() => {
    const canvas = gl.domElement;
    function onLost(event: Event) { event.preventDefault(); onUnavailable(); }
    canvas.addEventListener("webglcontextlost", onLost);
    // Keep the static plate until the first actual WebGL render has completed.
    let frame: number;
    const announce = () => {
      if (gl.info.render.frame > 0) onReady();
      else frame = requestAnimationFrame(announce);
    };
    frame = requestAnimationFrame(announce);
    return () => {
      cancelAnimationFrame(frame);
      canvas.removeEventListener("webglcontextlost", onLost);
    };
  }, [gl, onReady, onUnavailable]);
  return null;
}

export default function WorldCanvas(props: WorldProps) {
  const handles = useMemo(createWorldHandles, []);
  return <Canvas
    camera={{ fov: 38, near: 0.1, far: 100, position: [0, 0.6, 13] }}
    dpr={[1, 1.5]}
    frameloop="demand"
    flat
    gl={{ antialias: true, alpha: true, powerPreference: "low-power", toneMapping: NoToneMapping, outputColorSpace: SRGBColorSpace }}
    fallback={null}
    style={{ pointerEvents: "none" }}
  >
    <CameraRig handles={handles} />
    <ResearchWorld handles={handles} />
    {props.journeyReady && <ScrollCameraRig handles={handles} root={props.root} />}
    <WorldLifecycle {...props} />
  </Canvas>;
}
