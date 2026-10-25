import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { ANNULUS_CENTER, ANNULUS_INNER, ANNULUS_OUTER, arrivalCamera, createParticlePositions, createProjector, createSphereLines, SPHERE_CENTER, SPHERE_ROTATION, transformPoint, type Point3 } from "./sceneModel";
import styles from "./LandingPage.module.css";

export default function StaticWorldPlate() {
  const root = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 1440, height: 900 });
  useLayoutEffect(() => {
    if (!root.current || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width && height) setSize({ width, height });
    });
    observer.observe(root.current);
    return () => observer.disconnect();
  }, []);

  const drawing = useMemo(() => {
    const { width, height } = size;
    const project = createProjector(width, height);
    const view = arrivalCamera(width, height);
    const spherePoint = (point: Point3) => transformPoint(point.map((value) => value * view.sphereScale) as Point3, SPHERE_ROTATION, SPHERE_CENTER);
    const vertices = createSphereLines(width < 760 ? 16 : 24, width < 760 ? 10 : 16);
    let wire = "";
    for (let i = 0; i < vertices.length; i += 6) {
      const a = project(spherePoint(Array.from(vertices.slice(i, i + 3)) as Point3));
      const b = project(spherePoint(Array.from(vertices.slice(i + 3, i + 6)) as Point3));
      wire += `M${a[0].toFixed(1)},${a[1].toFixed(1)}L${b[0].toFixed(1)},${b[1].toFixed(1)}`;
    }
    const ring = [ANNULUS_OUTER, ANNULUS_INNER].map((radius) => {
      let path = "";
      for (let i = 0; i <= 160; i++) {
        const angle = i * Math.PI * 2 / 160;
        const p = project(transformPoint([radius * view.annulusScale * Math.cos(angle), radius * view.annulusScale * Math.sin(angle), 0], view.annulusRotation, ANNULUS_CENTER));
        path += `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`;
      }
      return path + "Z";
    }).join("");
    const particles = createParticlePositions(width < 760 ? 48 : 96);
    const dots = Array.from({ length: particles.length / 3 }, (_, i) => project(spherePoint(Array.from(particles.slice(i * 3, i * 3 + 3)) as Point3)));
    return { wire, ring, dots };
  }, [size]);

  return <div ref={root} className={styles.staticPlate}>
    <svg viewBox={`0 0 ${size.width} ${size.height}`} fill="none" aria-hidden="true" focusable="false">
      <path d={drawing.ring} className={styles.plateRing} fillRule="evenodd" />
      <path d={drawing.wire} className={styles.plateWire} />
      {drawing.dots.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={i % 9 === 0 ? 2.5 : 1.5} className={styles.plateParticle} />)}
    </svg>
  </div>;
}
