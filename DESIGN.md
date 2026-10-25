# DataOPedia — proposed design direction

**Status:** Approved visual direction for Phase 1 planning. Frontend implementation awaits approval of the implementation plan.

## Product and evidence boundary

DataOPedia is the proposed public name for the product currently called ResearchLens in the repository. Its task is to help students, researchers, and exploratory analysts move from a research question to a defensible first decision about public datasets. The workflow remains **question → interpretation → UCI discovery → deterministic profile → AI suitability interpretation → comparison → research decision**.

The available product definition is [docs/PRODUCT.md](docs/PRODUCT.md), supported by [docs/API.md](docs/API.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and the existing React interface. No separate PRD file is present in the repository. The design uses those documents as its requirements source. The present MVP searches UCI only; it has no publication index, saved projects, authentication, causal analysis, significance testing, or automated cleaning. Design concepts for unsupported data must say so in the interface.

## Visual concept: The Research Instrument

Treat the interface as a contemporary scientific instrument and an annotated research plate. Large editorial typography and controlled cinematic scale establish the landing page; disciplined tables, plots, rules, coordinates, and marginal notes organize the workspaces. Every line, node, number, and highlight has an informational role. A visitor should feel that they are inspecting evidence, not browsing a promotional dashboard.

The landing page's central visual is a **question-to-evidence map**. Before search it is a labeled schematic of the workflow, explicitly marked “Illustrative workflow”; after search it becomes the actual interpretation and verified dataset links. No sample number, publication connection, or statistical pattern is presented as live evidence. The map introduces the visual grammar reused in the graph, variable evidence, and analysis views.

The visual reference is the scale, editorial pacing, and data-led storytelling of [alethia.earth](https://www.alethia.earth/). DataOPedia uses its own research identity: technical annotation, bibliographic rhythm, a cool metal-like ground, aubergine type, and marigold selection marks. It does not borrow Alethia's environmental imagery or claims.

### Exploration and choice

Impeccable's direction seed was run for the landing surface. It assigned the third grounded direction. The candidate families considered were: (1) evidence ledger, (2) field atlas, (3) **research instrument plate**, (4) journal figure spread, (5) specimen index, (6) observatory console, and (7) archival finding aid. The instrument plate is selected because its coordinate system can hold both a spacious opening and dense statistical work without switching visual languages. The evidence ledger offered the strongest provenance discipline; its explicit source column is carried into every result and graph edge. The journal figure spread offered the strongest caption discipline; its figure labels and interpretation notes are carried into every visualization.

Other conceptual probes were judged against audience recognition and product clarity. A split-flap timetable could make status changes legible, but its fixed-cell typography would hinder long dataset names. A tiled narrative hall could structure a story, but it would compete with scientific plots. Textile, poster, and fashion-magazine systems offered striking motion or density, but weakened the reading of verified evidence. Their useful discipline is retained only where functional: clear state changes, section rhythm, and annotation density. None supplies a decorative motif.

## Information architecture and page layouts

The experience has one continuous research session. The question persists as a visible, editable context header. Navigation names the actual stage: **Question, Interpretation, Datasets, Graph, Analysis, Compare**. A stage that has no data remains an honest empty state rather than suggesting a completed computation. The landing is a Persuade surface; the other views are Operate surfaces.

| Surface | Desktop composition | Primary task and information order |
| --- | --- | --- |
| **Landing** | Editorial two-column opening. Left: oversized question prompt, one-sentence product claim, large multiline research input and a direct “Find datasets” action. Right: question-to-evidence map occupying the visual center, with fine coordinate ticks and a short legend. A narrow bottom strip explains UCI provenance, computed statistics, and AI interpretation. | Enter a question. The example prompt uses a noncausal wording such as “How is study time associated with academic performance?” and is identified as an example, not a finding. |
| **Research interpretation** | Wide question header; below it, a ruled interpretation sheet with four columns: subject/concepts, candidate independent variables, outcomes, population. A compact side note shows synonyms, 3–5 search terms, and processing mode. | Inspect the interpretation before judging results; revise the question and search again when its reading is wrong. Labels explicitly say “AI interpretation” or “Keyword fallback interpretation”; they are not verified dataset fields. |
| **Dataset discovery** | Two-column workspace: a narrow, persistent research context rail and a broad ranked results ledger. Each result is a full-width row with title, UCI ID, subject, instances, features, availability, preliminary relevance, confidence, and matched/missing variables. Expanding a row reveals descriptions, variable names, source URL, ranking explanation, and analysis action. | Scan provenance and coverage first; open original UCI page, analyze a dataset, or select up to three for comparison. Relevance is labeled “metadata-based”, never “suitability”. |
| **Knowledge graph** | Graph canvas on a measured grid plus a persistent detail inspector. Question/concept nodes lead to verified UCI dataset nodes; matched variable nodes appear only with evidence. An adjacent list reproduces every visible connection for scanning and keyboard use. | Follow why a candidate was surfaced. Edge labels state the relation and its basis. Publication nodes are omitted in the MVP unless a future verified bibliographic source supplies them. The empty publication layer explains “No verified publication links are available.” |
| **Dataset analysis** | A report-like page with a fixed summary masthead, then three aligned regions: evidence and suitability, quality/profile, and descriptive exploration. A variable table takes priority over decorative charts. A narrow right rail holds source, calculation and limitation notes. | Decide whether the dataset is worth further research. Inspect computed counts, missingness, duplicates, distributions, measurement types, role mappings, limitations, and the heuristic score only when available. |
| **Comparison** | Ruled matrix for 2–3 selected datasets, with shared criteria in rows and source-linked dataset headings in columns. Missing cells remain explicit. | Compare evidence, coverage, profile status, and limitations side by side; no automatic “winner” is implied. |

### First viewport and flow

At desktop width the opening view shows the name, a concise scientific promise, the complete question input, the primary action, and most of the question-to-evidence map without scrolling. The input is the focal point; the map answers what the system will do with the question. Search transitions into an interpretation sheet before the dataset ledger, making the model's reading inspectable. A user can always return to the question, inspect original repository metadata, and distinguish discovery from analysis.

## Visual system

### Color and provenance

| Role | Proposed token | Use |
| --- | --- | --- |
| Ice Silver | `#DDE3E8` | Main canvas and quiet data planes |
| Deep Aubergine | `#3A0F34` | Primary type, chart axes, active structural fields |
| Marigold | `#EAAA00` | Selection, active coordinate, focused evidence path, primary action accent |
| Paper | `#F6F7F6` | Reading surfaces and dense tables |
| Ink | `#201C24` | Long-form text on light surfaces |
| Muted ink | `#5F6269` | Secondary labels with checked contrast |
| Rule | `#AEB8C0` | Hairlines, row separation, axes; darker where needed for controls |
| Caution | `#8A3A2B` | Explicit error or important limitation only |

Avoid gradient fills and translucent panels. Aubergine carries identity rather than tinting every content block. Marigold marks active evidence or action; it never means “verified” on its own. Provenance is always a text label plus a source link or method note, so meaning survives grayscale and color vision differences.

### Typography

- **Display:** a high-contrast editorial serif for the landing title and major report headings; proposed choice is *Instrument Serif* or an equivalently legible editorial face after license and render checks. It conveys inquiry, with no faux academic flourishes.
- **Interface and reading:** *Geist* (already installed) or a similarly clear grotesk, regular through semibold. Body text targets 16–18 px with generous line height; result rows use a compact but readable 14–16 px range.
- **Data and annotation:** a restrained monospaced face for dataset IDs, coordinates, variable names, units, counts, statuses, and figure numbers. Do not set long prose in mono.
- **Hierarchy:** one large landing statement; 32–40 px section titles; 22–28 px report headings; 11–12 px uppercase or small-cap annotations with comfortable letter spacing. Dense labels must remain legible at 200% zoom.

### Grid, spacing, and surfaces

- Desktop uses a 12-column editorial grid with a 72–96 px outer margin on wide screens and a readable maximum text measure. Workspaces may span wider than the existing 960 px card column to fit comparison and plots.
- Baseline spacing is 8 px; major section intervals use 48, 72, or 96 px. Data rows use consistent vertical rhythm instead of individual floating cards.
- Fine dividers, axis rules, coordinate markers, numbered figures, source notes, and row indices form the interface grammar. Grid lines are visible only where they aid alignment or interpretation.
- Surfaces are square or minimally softened; controls have precise edges. Borders and typography separate information. Shadows are rare and reserved for a temporary inspector or overlay.
- Charts show units, denominator or `n`, scale, missing values, method, and a plain-language caption. Categorical encodings and ordinal variables must not be presented as continuous measurements.

## Component system

| Component | Contract |
| --- | --- |
| **ResearchQuestion** | Labeled multiline input, 10–2000 character validation, example prompt, submit/loading/error states, editable after search. |
| **EvidenceTag** | Textual provenance type: `UCI metadata`, `Computed profile`, `AI interpretation`, `Keyword fallback`, `Heuristic score`, or `Cached demo`. The label and explanation travel together. |
| **InterpretationField** | Concept or variable text, role, origin, uncertainty, and edit/research action where supported. An extracted phrase is never displayed as a measured column until verified. |
| **DatasetLedgerRow** | UCI title and ID, metadata summary, preliminary relevance and confidence, matched/missing variables, availability, source link, expand and analyze actions, comparison selector. |
| **EvidenceTrace** | A relation line with source and basis. Verified metadata and computed mappings use distinct text labels; inferred semantic links are explicitly marked as interpretation. |
| **GraphNode / GraphInspector** | Node type, label, source status, accessible focus target; selection reveals edge evidence and external source where present. List view mirrors graph content. |
| **ProfileMetric / VariableTable** | Exact count, denominator, measurement type, missing fraction, distribution or summary, and calculation provenance. Sort and expand without hiding relevant outcome and independent variables. |
| **SuitabilityBreakdown** | Six current criterion rows, nullable criterion values, explanations, and a clearly qualified Python-recomputed weighted heuristic total. Show “Unavailable” when assessment is unavailable. |
| **FigurePanel** | Descriptive SVG plot, data table, caption, method note, limitations, and text alternative. Never imply significance or causation. |
| **ComparisonMatrix** | 2–3 datasets, aligned evidence fields, explicit `Not analyzed` / `Unavailable` cells, and source links. |
| **StatusNotice** | Loading, empty, timeout, retry, UCI failure, Gemini fallback, metadata-only, AI unavailable, and DEMO_MODE states with concrete next action. |

## Interaction and motion

- The signature interaction is **trace the evidence**: selecting an interpreted concept highlights its matched metadata in the ledger and, where verified, its variable path in the graph and analysis. The inspector explains each connection. A highlighted path is an aid to reading, never proof of a relationship.
- Opening a dataset shifts it from a scan row into a structured evidence sheet. The original source URL stays visible. Analyze is an explicit action because profiling can take time.
- Search and analysis use visible progress language for their synchronous request stages; no fake live stream or percentage. Timeouts preserve the question and offer retry. Gemini fallback is called out without hiding usable UCI results.
- Graph pan, zoom, select, reset, and “fit evidence” are available by pointer and keyboard. The list view is the reliable alternative to spatial navigation. An edge requires a corresponding inspector explanation.
- Motion is measured: 150–250 ms focus/selection transitions, subtle line reveal for a newly loaded verified path, and no continuous ambient animation in workspaces. Respect reduced-motion preference. The landing map can stage a single short entrance, with all information present when motion is disabled.

## Responsive behavior

Design desktop first, then adapt without changing the evidence order. At tablet widths the context rail becomes a collapsible top summary; the result ledger compresses less important columns into a detail region. On phones the question and one primary action remain in the first viewport, the map becomes a vertical sequence, results become ruled stacked records, and the graph defaults to an evidence list with an optional pan/zoom canvas. Analysis tables allow deliberate horizontal scrolling with sticky variable names or a compact row detail view. Comparison uses per-criterion stacked rows rather than tiny columns. Source labels, caveats, and `n` values remain adjacent to the numbers they qualify.

Keyboard focus is visible in aubergine with a marigold offset marker. All charts have a caption and accessible data equivalent. Controls meet touch target needs; text and data remain usable at 200% zoom. Color never serves as the only source or state indicator.

## Scientific integrity rules

1. **Verified repository metadata** includes UCI identity, source URL, supplied descriptions, counts and variables. It is labeled `UCI metadata` and linked to the original record.
2. **Deterministic computation** includes the Pandas/NumPy profile and grouped descriptive statistics. It is labeled `Computed profile`, with denominators and measurement assumptions visible.
3. **AI inference** includes research question interpretation, semantic relevance explanation, and assessment narrative. It is labeled `AI interpretation` or `AI assessment`; fallback mode is named when used.
4. **Heuristic scores** are separate: discovery relevance is metadata-based; suitability requires inspected data and validated criteria. A number never appears without its type, confidence or availability, and explanation.
5. **Unknown is a first-class state.** Missing variables, unsupported publication links, unavailable AI assessment, and metadata-only records retain explicit empty values. No invented datasets, publications, citations, scores, links, or analyses enter mockups or UI copy as facts.
6. **Method limits remain visible.** Records are not necessarily independent people; encoded ordinal values are not exact physical units; descriptive association is not causation; no significance or power claim appears without actual supported analysis.

## Review decisions and implementation boundary

The proposed brand name DataOPedia is assumed to replace ResearchLens in visible UI copy after approval; repository and backend renaming is outside this design phase. The graph is a planned frontend experience using actual question, UCI dataset, and verified variable evidence. Publication connectivity is a future, source-dependent layer and must not be populated from model inference. The existing React/Vite frontend, API models, UCI-only scope, three-dataset comparison limit, and DEMO_MODE disclosures remain constraints.

This file proposes the visual and interaction contract only. After review, implementation can be planned against the existing frontend and checked at desktop and mobile sizes. No backend functionality, publication ingestion, or statistical method is part of this design proposal.
