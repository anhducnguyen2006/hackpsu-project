import type { Material } from "three";

/** Fade lines and points before the near plane, avoiding hard cuts during passage. */
export const softenNearGeometry: Material["onBeforeCompile"] = (shader) => {
  shader.fragmentShader = shader.fragmentShader.replace(
    "#include <fog_fragment>",
    "#include <fog_fragment>\n gl_FragColor.a *= smoothstep(0.15, 1.2, vFogDepth);",
  );
};
