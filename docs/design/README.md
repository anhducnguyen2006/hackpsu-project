# UI/UX Design System

Last verified: 2026-10-24

## Philosophy

The interface is a light, evidence-oriented research dashboard. It favors readable cards, explicit provenance, restrained blue accents, and visible uncertainty over dense visualization or decorative complexity.

## Current visual tokens

Defined in `frontend/src/styles.css`:

- Page background: `#f4f7fb`
- Primary text: `#1f2937`
- Muted text: `#64748b`
- Primary blue: `#2563eb`
- Dark blue text: `#1d4ed8`
- Borders: `#dbe3ef` and `#cbd5e1`
- White cards: `#fff`
- Success score badge: `#dcfce7` background and `#166534` text
- Content max width: `960px`
- Page padding: `64px 24px`
- Card radius: `16px`
- Control radius: `10px`

Typography uses Inter when available, followed by system UI fonts. Headings use a responsive `clamp` size and tight letter spacing.

## Components and interactions

- Search panel: question label, text input, and primary Search button
- Dataset card: source, title, description, comparison checkbox, metadata relevance pills, and an explicit Details/Hide details button
- Analysis report: profile, suitability status, evidence, statistics, and limitations
- Exploratory report: descriptive SVG chart, values, counts, and non-causal disclaimer
- Comparison view: selected dataset cards with provenance, status, variables, and limitations
- Warning/error states: explicit fallback, cached, timeout, retry, and unavailable labels

The Details control owns dataset expansion; nested controls have independent state and do not collapse the card. Semantic buttons use `type="button"` and the Details control exposes `aria-expanded` and `aria-controls`.

## Responsive behavior

The main layout is a centered single-column dashboard. Search controls and dataset grids adapt at the mobile breakpoint. The SVG exploratory chart uses a viewBox and scales to its container. Long metadata and comparison content can require vertical scrolling.

## Accessibility principles

Use labels for inputs, semantic buttons, visible focus/keyboard operation supplied by native controls, meaningful status text, and descriptive SVG alternatives. Future work should add automated accessibility checks and more explicit live-region announcements.
