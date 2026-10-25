# DataOPedia themes

The theme system preserves the existing composition, typography, data, interaction and light palette. Dark mode continues the scientific visual identity with Charcoal, Earth Brown and Burned Amber.

## Color audit

The actual entrypoint imports `styles/foundation.css`, `landing.css`, `workspace.css`, `graph.css` and `analysis.css`. The cinematic landing page additionally loads CSS modules. The original hardcoded colors were distributed across:

| Source | Original literals / roles | Implementation |
| --- | --- | --- |
| `styles/foundation.css` | Ice Silver `#DDE3E8`, Deep Aubergine `#3A0F34`, Marigold `#EAAA00`, paper `#F6F7F6`, ink `#201C24`, muted `#5F6269`, rule `#AEB8C0`, caution `#8A3A2B`, white action text | Semantic background, surface, heading, accent, text, muted, border, danger and action roles |
| `styles/landing.css` | Workflow borders `#826b7b`, captions `#d3c2ce` | Inverse surface, text, muted and border roles |
| `styles/analysis.css` | Chart guides `#d8dcdf` | Chart guide token; axes, labels, points and stems already consumed shared colors |
| `styles/graph.css` | Graph ink/muted, white inputs, translucent paper panels/tooltips/toolbars, aubergine shadows/borders, white label halo, teal focus, yellow/lilac halos, dotted grid and connection key | Separate semantic graph, input, panel, toolbar, tooltip, shadow, focus, halo and connection tokens, preserving every original alpha value in light mode |
| `landing/palette.ts`, landing materials | Four fixed brand colors in fog, ring, sphere, particles and frames | Retain original constants for deterministic helpers; sample animated CSS tokens into existing materials |
| `landing/collageSequence.ts`, `ScrollCameraRig.tsx` | Aubergine and `#060010` cinematic backgrounds, contrasting navigation ink | GSAP animates numeric scene phases; background and navigation ink derive from theme colors and current scene phase |
| Landing CSS modules and `EvidenceWall.tsx` | Black/violet cinema surfaces; gray foregrounds; light actions; image scrims; white focus and translucent shadows | Cinema, media, inverse and on-accent tokens; image content retains its original colors |
| `SigmaGraph.tsx` | Seven node-kind colors, inferred/verified edge colors and label ink | Node/edge tokens update graph attributes in place |
| `ResearchConnectionsGraph.tsx` | Node ink/paper/border, muted relationship edges and Marigold selections/shared edges | Complete themed Cytoscape stylesheet updated on the existing instance |
| `graph/intro/GraphIntro.tsx` | Lilac particles `#A895D0` and cyan lines `#81C9D6` | Theme-aware particle/line tokens |
| `landing/react-bits/DriftWall.module.css` | Placeholder fill, dark shadow and white focus ring | Media placeholder, scrim and text tokens |

`src/styles.css` is an unused legacy blue/gray stylesheet, with no imports in the application. It is deliberately excluded from the active theme refactor. Self-contained editorial SVGs, photographs, upstream reference text and black alpha masks remain image/mask content, rather than UI theme colors. Only the four original constants and the pre-CSS bootstrap/browser-chrome background colors remain fixed in application code. `styles/theme.css` contains the complete active color inventory and exact light/dark values.

## Palette roles

| Role | Light | Dark |
| --- | --- | --- |
| Page | `#DDE3E8` | `#090907` |
| Surface | `#F6F7F6` | `#171610` |
| Text | `#201C24` | `#F4EFE6` |
| Heading / links | `#3A0F34` | `#D2BA95` |
| Muted text | `#5F6269` | `#B6AD9E` |
| Border | `#AEB8C0` | `#80705A` |
| Secondary / filled action | `#3A0F34` | `#6C5636` |
| Accent | `#EAAA00` | `#B99D73` |

Earth Brown also colors the dark scene’s ring so that overlapping large headings retain 3:1 contrast and supporting text retains 4.5:1; light-mode geometry and Marigold remain unchanged. Earth Brown is a filled-surface color with a pale foreground. Brightened brown/amber shades provide readable headings and borders. Dark-mode text roles meet 4.5:1 contrast on reading surfaces; structural borders meet 3:1. Native controls use the appropriate `color-scheme`; placeholders have an explicit accessible color.

## Architecture and implementation sequence

1. Audit actual imports, CSS modules, SVGs and both canvas renderers. Preserve the light values at each declaration rather than stacking dark-only component overrides.
2. Add `styles/theme.css` with `[data-theme="light"]` and `[data-theme="dark"]` semantic tokens. Existing brand variable names remain aliases so established selectors and component layouts survive.
3. Resolve `dataopedia-theme` from localStorage in the blocking `public/theme-init.js` head script. Use the OS preference when storage is absent, invalid or inaccessible; set the initial background and browser chrome before React loads.
4. `theme/theme.ts` synchronizes React subscribers, OS changes and other tabs. Explicit preferences persist; blocked storage falls back to an in-memory preference. Both headers expose the same keyboard-accessible 44px sun/moon toggle.
5. Animate registered `<color>` custom properties on the document root for 400ms ease-in-out. Backgrounds, foregrounds, borders, SVG fills/strokes, shadows and scrims inherit the interpolation. Do not override element transition lists, animate transforms/layout or introduce `transition: all`. Enable theme transitions after initial initialization and only with `prefers-reduced-motion: no-preference`.
6. `observeThemeColors` samples those same interpolated values for 450ms after a change (including a final settled frame). Update canvas styles/material colors without resetting graph data, selection, coordinates, camera, physics, scene instances, scroll progress or GSAP timelines. Cancel observation frames/listeners on cleanup.
7. Verify preference behavior, first-load bootstrap, contrast, renderer preservation, production compilation and responsive browser rendering. Compare original and updated light-mode computed styles using an unchanged temporary copy of the frontend.

## Validation

Final automated verification: 89 tests passed across 30 files; the production build passed.

Run from the repository root:

```sh
npm --prefix frontend test
npm --prefix frontend run build
```

Tests cover OS changes, saved/invalid preferences, unavailable storage, cross-tab changes, accessible toggle state, pre-React theme initialization, renderers mounting during a transition, dark-mode contrast and preservation of both graph instances during color updates. Existing navigation, discovery, analysis, graph, landing timeline and reduced-motion tests remain part of the suite.

Real Chromium checks cover landing and dashboard at 1440, 768, 390 and 320px in both themes, the dataset ledger, analysis with its SVG chart, and Sigma. Checks include intermediate transition colors, preserved question input, persisted preference after reload, canvas element identity, reduced-motion static fallback, pre-React dark background, horizontal overflow and comparison with original light computed styles. Screenshots and the browser report are stored locally in `/private/tmp/dataopedia-theme-check/`.

No backend data, API behavior, photography, dependencies or graph layout algorithms change. Production output retains the existing large-chunk warning. Modern browsers supporting registered CSS custom properties animate the palette; older browsers still receive the final theme colors.
