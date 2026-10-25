# DataOPedia: a continuous cinematic research world

## 1. Creative direction and visual storyboard

Build one spatial journey at `/landing`: an enormous scientific structure opens into a field of possibilities, forms connections, and settles into precise geometry.

Keep the existing application at `/` unchanged. This specification supersedes the earlier static foundation proposal. Implementation and dependency installation require approval; saving this plan does not authorize implementation. Supabase authentication, configuration, and all backend integration remain outside scope.

**Art direction:** retain `DESIGN.md`’s research-instrument identity. Use [Alethia](https://www.alethia.earth/) as a reference for spatial storytelling and pacing; the compositions and choreography below are original proposals.

- **Ice Silver `#DDE3E8`:** continuous ground throughout the journey.
- **Deep Aubergine `#3A0F34`:** typography, wireframes, and network structure.
- **Marigold `#EAAA00`:** large circular forms, selected nodes, and the research action.
- **Paper `#F6F7F6`:** restrained reading surfaces and contrast protection.
- Unlit, precise geometry with depth and parallax. Avoid glossy materials, gradients, bloom, floating cards, and conventional feature grids.
- Persist the annotation **“Illustrative research geometry.”** Nodes, links, and coordinates describe the illustration; they must not imply verified datasets or findings.

The percentages below describe **narrative progress**, rather than elapsed time.

| Stage | Visual storyboard | Spatial transition | Typography |
|---|---|---|---|
| **Arrival — 0–20%** | An aubergine wireframe sphere exceeds the viewport height and is cropped across the right edge. Sparse particles occupy its shell. A broad marigold annulus appears behind its lower hemisphere. Fine coordinate lines establish scale. | A restrained forward drift establishes depth. The sphere rotates slowly while the visitor rests near the beginning. | **“Every question / opens a world.”** Oversized serif type occupies the left foreground. First line, supporting sentence, and preview link are immediately available; remaining lines reveal with the first scrolling movement. |
| **Descent — 20–48%** | The sphere expands beyond the frame as the camera crosses its surface. Near meridians pass the viewport edges; distant particles remain visible through the hollow structure. Shell particles spread into a deep field. | Travel through the sphere, with foreground lines moving faster than background geometry. Continue through its rear surface without a cut, blackout, or replacement scene. | **“Move beyond / the surface.”** Type becomes more restrained, allowing the passage through geometry to dominate. Supporting copy introduces variables, coverage, and limitations. |
| **Discovery — 48–78%** | The same particles gather into three asymmetric clusters. Connections emerge gradually between selected anchors. Marigold circular forms remain behind the network as reference planes. | Forward travel becomes a lateral track. Foreground anchors pass across distant clusters, making their separation legible. | **“Connections / need context.”** The heading occupies a quiet upper-left area while the network crosses the central field. Body copy remains stationary while readable. |
| **Resolution — 78–100%** | Clusters reorganize into an exact three-dimensional coordinate lattice. Measurement frames align with it. A marigold annulus frames the resulting structure. | Camera and geometry settle by 94%. The final 6% provides a stable reading and action interval. | **“Begin with / better questions.”** The research action gains prominence: **“Open research preview” → `/`**. Explain that the destination is the existing cached preview. |

**Typography choreography**

Use landing-scoped Instrument Serif Regular, existing Geist for interface text, and system monospace for scientific annotations. Self-host the serif with its license; use Georgia while it loads.

Headings use line wrappers, with a maximum entrance displacement of approximately one line height. Each chapter’s lines settle during its opening 12%; they lift slightly as the chapter exits. No character-by-character scrambling. Body text does not animate.

The arrival reveal belongs to the scroll timeline, so immediate scrolling advances it immediately. No mandatory introduction or loading sequence. Interactive links never depend on an opacity reveal to become usable.

## 2. Camera, geometry, and particle transformations

### Camera specification

Use one perspective camera, right-handed coordinates, positive Y upward, and no camera roll.

- Desktop vertical field of view: **38°**.
- Portrait vertical field of view: **52°**.
- Near/far planes: **0.05 / 100** world units.
- Initial sphere: center **`(3, 0, 0)`**, radius **`5.8`**.
- All coordinates below are illustrative world units.

Each cell gives **camera position → look-at target**.

| Progress | Desktop | Portrait |
|---|---|---|
| **0%** | `(0, .6, 13)` → `(1.2, 0, 0)` | `(3, .8, 12.5)` → `(3, -1.3, 0)` |
| **20%** | `(.8, .35, 10)` → `(2.4, 0, -3)` | `(3, .35, 9.5)` → `(3, -.3, -3)` |
| **34%** | `(2.2, .1, 3)` → `(3, 0, -9)` | `(3, .1, 3)` → `(3, 0, -9)` |
| **48%** | `(3, -.2, -6.6)` → `(4, 0, -16)` | `(3.1, -.2, -6.6)` → `(4, 0, -16)` |
| **64%** | `(6.3, .4, -8.3)` → `(4, 0, -17)` | `(5.1, .25, -8.1)` → `(4.5, 0, -17)` |
| **78%** | `(8, .6, -10)` → `(3, 0, -18)` | `(6, .45, -9.2)` → `(4.5, -.7, -18)` |
| **94%** | `(8.2, .6, -10.5)` → `(2.2, 0, -18)` | `(6.2, .45, -9.6)` → `(4.5, -1.5, -18)` |
| **94–100%** | Hold final pose | Hold final pose |

Interpolate position and target along open centripetal Catmull–Rom curves. Map narrative progress to their parameters using a monotone, continuously differentiable curve with zero endpoint velocity. This preserves smooth travel across stage boundaries and provides a deliberate final stop.

Do not add independent camera damping: restored positions, rapid scrolling, and reverse scrolling must reproduce the same authored pose.

### Persistent geometry

Keep these objects mounted throughout the journey:

- One combined sphere wireframe: 24 meridians and 16 parallels on desktop; reduced detail on phones.
- One particle system.
- Two preallocated connection graphs for clustered and resolved arrangements.
- Three marigold annular forms sharing geometry and material.
- Batched coordinate frames and measurement lines.

Objects pass behind the camera or recede into depth; stage changes do not replace the scene.

### Particle transformation

Generate **5,832 canonical particle IDs**, corresponding to an **18 × 18 × 18** final lattice. Precompute four positions for every ID:

1. A distributed position on the sphere shell.
2. A position in a volumetric corridor extending through the sphere.
3. A position within one of three clusters centered at `(1, 1, -15)`, `(5, -.7, -17)`, and `(7, 1.4, -19)`.
4. A unique lattice position centered at `(4.5, 0, -18)`.

The final lattice’s desktop dimensions are **6 × 4 × 3 world units**, with spacing `6/17`, `4/17`, and `3/17`. These dimensions describe its physical extent, not its particle count.

Portrait rendering compresses the final extent to **2.6 × 2.2 × 1.8 units**, keeping the resolved structure above the final copy. Cluster and corridor targets receive corresponding horizontal compression.

Morph positions in the vertex shader:

- **20–48%:** sphere → corridor.
- **48–78%:** corridor → clusters.
- **78–94%:** clusters → lattice.
- **94–100%:** hold.

Use smooth endpoint easing for each morph. Generate buffers once; animate uniforms instead of reallocating vertices or creating React elements per particle.

Connections use the same endpoint interpolation as their particles. Precompute sparse graphs; fade clustered connections into lattice connections during Resolution. No runtime nearest-neighbor search or physics simulation.

Provide conservative bounds encompassing every morph target, near-camera fading, and capped particle sizes to prevent clipping flashes and excessive overdraw.

## 3. GSAP strategy and React architecture

### Scroll and timeline ownership

Use one GSAP master timeline and one ScrollTrigger:

- Trigger: the landing story root.
- Start: `top top`.
- End: `bottom bottom`.
- Scrub: **0.45 seconds desktop**, **0.2 seconds mobile**.
- Native document scrolling; no snapping, wheel interception, custom scroller, or scroll proxy.
- Persist the viewport using CSS `position: sticky`; ScrollTrigger does not need to pin it.

Default journey lengths:

- **Desktop:** nine viewport heights total, producing eight viewport heights of scroll travel.
- **Phone:** six viewport heights total, producing five viewport heights of travel.

Use stable viewport units. Chapter rails may grow to accommodate text, font changes, or zoom.

**Measured chapter positions own synchronization.** The timeline advances a normalized physical scroll value. A continuous mapping converts measured chapter boundaries to the authored narrative checkpoints `0 / .20 / .48 / .78 / 1`. Camera motion, morphing, and typography therefore remain aligned when chapter heights change.

Use named timeline labels for Arrival, Descent, Discovery, Resolution, and Settle. Child tweens have no independent ScrollTriggers. This follows GSAP’s documented timeline and scrub model. [ScrollTrigger documentation](https://gsap.com/docs/v3/Plugins/ScrollTrigger/)

### State and lifecycle

GSAP owns scroll progress and HTML heading transforms. R3F’s frame callback reads a shared ref, evaluates the world state, and applies camera and material values. Avoid React state updates during scrolling.

Ambient rotation is separate, delta-based motion on the arrival shell. It tapers to zero by 20% and stops while hidden, offscreen, or reduced motion is active.

Use scoped `useGSAP()` and `gsap.matchMedia()` for lifecycle and responsive behavior. Revert owned animations and listeners on cleanup; never kill unrelated global triggers. Refresh measurements after fonts load and meaningful layout changes. [GSAP React integration](https://gsap.com/resources/React/)

### Component responsibilities

All new scene code and styles live under `frontend/src/landing/`.

| Component/module | Responsibility |
|---|---|
| **LandingPage** | Semantic chapter rails, copy, controls, scoped styles, and static fallback. |
| **CinematicExperience** | Lazy loading, error boundary, scene readiness, and timeline bridge. |
| **WorldCanvas / ResearchWorld** | One persistent canvas containing CameraRig, WireSphere, ParticleField, ConnectionField, and ScientificFrames. |
| **useWorldTimeline** | Measurements, master timeline, chapter mapping, responsive cleanup. |
| **worldModel / storyConfig** | Seeded positions, camera checkpoints, interpolation, copy, and quality budgets. |
| **Particle materials** | Shared morph calculations for points and connection endpoints. |

Add the previously proposed `AppEntry` selector and change `main.tsx` only to mount it. Exact `/landing` and `/landing/` load the new experience; every other pathname preserves existing behavior.

After approval, add Three.js, **React Three Fiber 8**, GSAP, and `@gsap/react`, with compatible versions locked. Preserve React 18: Fiber’s official documentation pairs React 18 with Fiber 8. [R3F installation guidance](https://r3f.docs.pmnd.rs/getting-started/installation)

The dashboard must not request the landing’s Three.js or GSAP chunks. No router package, backend integration, API calls, or global stylesheet changes are required.

## 4. Responsive behavior, accessibility, and performance

**Phones retain the complete journey**, as selected: the sphere fly-through, lateral discovery, and final transformation remain. Use the portrait camera checkpoints, compressed geometry, shorter scroll travel, and lower rendering budgets.

| Budget | Desktop | Phone |
|---|---:|---:|
| Visible particles | 5,832 | 1,728 |
| Maximum connection segments, combined | 900 | 300 |
| Device pixel ratio cap | 1.5 | 1 |
| Draw-call target | ≤12 | ≤8 |
| Performance target | 60 fps | ≥30 fps |

Order canonical IDs using seeded, stratified buckets covering sphere octants, lattice octants, and cluster membership. Interleave those buckets before generating draw ranges. Phone and lower-quality subsets must retain the whole composition rather than a cap of the sphere.

If frame cost remains above budget during active scrolling, lower pixel ratio first, then particle and edge counts. Use an additional **864-particle** tier without remounting the canvas.

Use unlit materials and correct sRGB output conversion to preserve palette colors. No shadows, postprocessing, external models, video, or particle textures.

Use demand rendering: timeline updates invalidate the canvas; arrival ambient motion requests frames only while active. Once Resolution settles, rendering becomes idle. R3F explicitly supports this rendering model. [R3F performance guidance](https://r3f.docs.pmnd.rs/advanced/scaling-performance)

**Accessible behavior**

- HTML headings and paragraphs remain in semantic document order, within normal-flow chapter rails.
- Body copy remains stable while being read. Text and controls receive protected clear areas.
- Maintain a persistent preview link and a skip link to the final research action.
- Use visible keyboard focus, 44-pixel interaction targets, and aubergine text on marigold controls.
- Decorative canvas content is excluded from the accessibility tree.
- Provide a **“Reduce motion”** control. System reduced-motion preference takes precedence.
- Reduced motion uses a static SVG scientific plate and all four chapters in ordinary reading flow, with no extended cinematic scroll length or 3D initialization.
- WebGL failure or context loss uses the same readable fallback.
- Loading never blocks HTML or CTA access. Reveal the canvas only after its first frame matches the current scroll position.
- Preserve focus and chapter context across preference, layout, and orientation changes.

## 5. Implementation milestones and approval criteria

| Milestone | Testable visual result |
|---|---|
| **1. Establish the visual composition** | `/landing` shows the oversized sphere plate, approved typography, palette, four narrative texts, and working preview links. Desktop and portrait captures establish composition. Existing `/` remains unchanged. |
| **2. Build the continuous camera flight** | One live canvas presents the complete wireframe journey. Seeking to every camera checkpoint produces the specified framing. Forward, backward, and rapid scrolling cross stage boundaries without cuts, orientation flips, or scene resets. |
| **3. Complete the scientific transformation** | The same particle IDs progress through shell, corridor, clusters, and lattice. Connections stay attached during movement. Captures at 34%, 64%, and 94% demonstrate distinctly different spatial states. |
| **4. Choreograph typography and pacing** | Heading reveals, reading intervals, camera travel, and final CTA emphasis work together. The complete portrait journey remains composed around readable text. Increased text size does not desynchronize chapters. |
| **5. Harden responsive and fallback behavior** | Reduced motion, WebGL failure, context loss, restored scroll, orientation changes, and route exit all behave correctly. Rendering meets the documented budgets on tested devices, with any untested physical-device coverage disclosed. |

Verification includes:

- Existing frontend tests and production build.
- Pure-model tests for seeded determinism, finite camera poses, morph endpoints, and spatial coverage at lower particle budgets.
- Routing and accessible DOM tests, including reduced-motion initialization.
- Browser captures immediately before and after 20%, 48%, and 78%, plus all settled checkpoints.
- Real WebGL checks for rapid seeking, reverse scrolling, history restoration, and StrictMode cleanup.
- Dashboard visual regression checks and confirmation that `/` loads no cinematic runtime chunks.
- Keyboard operation, 200% zoom, and confirmation of no API requests.

Implementation begins only after approval. Saving this specification changes no application code, dependencies, global styles, or backend configuration.
