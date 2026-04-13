# Scientific Presentation Diagram Style Guide (PaperBanana-Distilled)

```
NOTICE
=====================================================================
This document is adapted from PaperBanana
(https://github.com/dwzhu-pku/PaperBanana),
© 2026 Google LLC, licensed under Apache License 2.0.

Source file:   style_guides/neurips2025_diagram_style_guide.md
Source commit: main branch as of 2026-04-11 (specific commit hash to
                be recorded in references/VERSIONS.md when the plugin
                is first packaged for release)

Modifications (Apache-2.0 §4(b)):

- Retargeted the audience framing from NeurIPS 2025 ML/AI paper authors
  to biomedical/neuroscience researchers giving lab meetings, seminars,
  conference talks, and journal clubs.
- Replaced PaperBanana's Section 4 "Domain-Specific Styles" (which
  covered Agent/LLM, Computer Vision/3D, and Theoretical/Optimization
  paper subdomains) with four biomedical-research subdomains: Clinical
  & Translational, Wet-lab & Bench Science, Neuroscience & Imaging,
  and Computational & Modeling.
- Added a new Section 5 "Applying this guidance to Debrief's diagram
  libraries" with practical mappings to Mermaid, rough.js, and inline
  SVG — the three permitted diagram libraries in Debrief's
  style_config.json constraints.permitted_diagram_types.
- Generalized PaperBanana's ML-specific iconography options (brain as
  LLM, chat bubble as prompt, etc.) to a broader set of general-purpose
  scientific icons.
- Retained VERBATIM (marked inline below): the aesthetic principles in
  Section 1 ("Soft Tech & Scientific Pastels", "Softened Geometry"),
  the four Zone Strategy background hex codes (#F5F5DC, #E6F3FF,
  #E0F2F1, #F3E5F5), the color-pairing heuristics, the line/arrow
  semantics, the typography rules, and the entire Section 3 "Common
  Pitfalls" list.

Modified by:        Carlo Fusco and Leonardo Restivo
Modification date:  2026-04-11
License:            Apache-2.0 (inherited)

PATENT NOTICE — The PaperBanana README states that patents have been
filed by Google covering the multi-agent pipeline workflows (Retriever
→ Planner → Stylist → Visualizer → Critic). This file reuses ONLY
documentation content (visual design guidance), not the multi-agent
architecture. See ${CLAUDE_PLUGIN_ROOT}/NOTICE for the full patent
disclosure.

The upstream file is available at:
https://github.com/dwzhu-pku/PaperBanana/blob/main/style_guides/neurips2025_diagram_style_guide.md
=====================================================================
```

---

## Purpose

This file is **craft-knowledge baseline** for diagram aesthetics in scientific presentations. It is loaded by the Debrief **Stylist** agent during every Phase 2 style dialog (per Section 22.8 Stylist row "Always Loaded" column and REQ-STYLE-2 step 2). Unlike `paperbanana-derivation-meta-prompt.md` (which is instructions about HOW to derive a style guide from reference images), this file provides CONTENT KNOWLEDGE about what well-designed scientific-presentation diagrams look like.

The Stylist consults this file when producing `style_guide.md` for any project — whether or not the user imported a reference file. When a project has NO imported reference, this file (together with the sibling `paperbanana-plot-style-distilled.md` and `ai4vis-survey-distilled.md`) is the primary source the Stylist draws on.

**Sibling files in `${CLAUDE_PLUGIN_ROOT}/references/`:**
- `paperbanana-plot-style-distilled.md` — data-visualization aesthetics (the plot/chart counterpart to this file)
- `ai4vis-survey-distilled.md` — academic grounding in visualization design principles
- `paperbanana-derivation-meta-prompt.md` — meta-prompt instructing the Stylist how to derive a style guide from reference images (loaded only in reference-derivation mode)

---

## 1. The Scientific Presentation Look

The aesthetic standard this guide codifies centers on **"Soft Tech & Scientific Pastels."** Rather than employing sharp primary colors and harsh black outlines, contemporary scientific presentation diagrams prioritize approachability alongside precision. They leverage high-value light backgrounds to manage visual complexity while reserving color saturation for essential active components. The design philosophy merges **clean modularity** with **narrative flow**, establishing a left-to-right reading pattern for process diagrams and a hierarchical grouping pattern for conceptual diagrams.

Core principles:

- **Approachability + precision.** Diagrams should invite the reader in without sacrificing rigor.
- **High-value light backgrounds.** Most of the slide is pale; color intensity is a resource to spend sparingly.
- **Saturation as emphasis.** Fully-saturated colors are reserved for the 1-2 elements that matter most (the key finding, the active pathway, the highlighted result).
- **Modularity.** Clear visual regions with explicit boundaries. Every element should belong to a visually named zone.
- **Left-to-right narrative flow.** Inputs enter from the left, processing happens in the middle, outputs/conclusions emerge on the right. Branches and feedback loops are the exception, not the rule.

---

## 2. Detailed Style Options

### A. Color Palettes

**Design Philosophy:** Employ color to structure logic, not merely embellish. Steer clear of fully saturated background fills.

**Background Fills (The "Zone" Strategy)**

Zones encapsulate stages (e.g., "Data acquisition", "Analysis", "Interpretation") or operational contexts (e.g., "In vivo experiment", "Computational pipeline").

- **Standard approach:** Very light, desaturated pastels at approximately 10-15% opacity (or 90-95% lightness in HSL terms).
- **Recommended starter palette** (preserved verbatim from upstream):
  - 🍦 **Cream / Beige** (`#F5F5DC`) — Warm, scholarly aesthetic
  - ☁️ **Pale Blue / Ice** (`#E6F3FF`) — Technical, clean impression
  - 🌿 **Mint / Sage** (`#E0F2F1`) — Soft, natural quality
  - 🌸 **Pale Lavender** (`#F3E5F5`) — Distinctive, contemporary feel
- **Alternative (~20% of presentations):** White backgrounds paired with colored dashed borders for a high-contrast, minimalist presentation (prevalent in theoretical and mathematical-modeling contexts).

**Functional Element Colors**

For "Active" modules (processes, analyses, key results), medium saturation proves most effective.

- **Typical pairings** that work well together: Blue/Orange, Green/Purple, or Teal/Pink.
- **Status differentiation through color:**
  - **Active / In-progress elements:** Warm tones (red, orange, deep pink) — draw the eye
  - **Stable / Reference elements:** Cool tones (grey, ice blue, cyan) — recede visually
- **Highlights / Key results:** High saturation is reserved strictly for critical outputs — the headline finding, the p-value that matters, the treatment effect. If everything is highlighted, nothing is.

Common choices include one dominant hue (60% of the palette), one secondary hue (30%), and one accent hue (10%). This is the well-known 60/30/10 rule applied to slide design.

### B. Shapes & Containers

**Design Philosophy:** Apply **"Softened Geometry"** — sharp corners indicate data; rounded corners suggest processes.

**Core Components**

- **Process Nodes:** Rounded Rectangles (5-10px corner radius) dominate (~80%) for steps, analyses, or stages.
- **Data / Samples:**
  - **3D Stacks / Cuboids:** Communicate volume or multi-dimensional data (e.g., a patient cohort with multiple measurements per subject, a stack of confocal image slices)
  - **Flat Squares / Grids:** Represent matrices, tables, or 2D fields (e.g., a gene-expression matrix, a connectivity matrix, a pixel grid)
  - **Cylinders:** Reserved exclusively for databases, biobanks, or memory/storage stores

**Grouping & Hierarchy**

- **The "Macro-Micro" Pattern:** A light-colored encompassing container represents the broader context (e.g., "The whole pipeline"); specific modules connect via callout lines to detailed breakout visualizations ("Zoom into step 3: the clustering algorithm").
- **Borders:**
  - **Solid:** Physical components, confirmed pathways, concrete data
  - **Dashed:** Logical stages, hypothetical connections, optional pathways, or scope boundaries

### C. Lines & Arrows

**Design Philosophy:** Line appearance communicates flow classification. The reader should be able to tell "what kind of thing is flowing" just from the line's style, without reading the label.

**Connector Styles**

- **Orthogonal / Elbow:** Most slides use this for structured pipelines and process flows (implies precision, structured data movement, predictable ordering).
- **Curved / Bezier:** Favored for biological pathways, feedback loops, conceptual relationships, or anywhere the connection represents influence rather than a discrete transfer.

**Line Semantics**

- **Solid Black / Grey:** Forward flow (standard data or information movement from source to sink)
- **Dashed Lines:** Auxiliary pathways — feedback, inhibition, optional connections, hypothesized influence, or statistical relationships
- **Dotted Lines:** Weak or speculative connections (use sparingly)
- **Colored Arrows:** Activation (green), inhibition (red), modulation (purple) — common in biology-focused diagrams. The specific color→semantic mapping is project-specific; document it in the style guide so the audience can read the diagram without a legend.
- **Mathematical Operators:** Standard symbols ($\oplus$ for addition/combination, $\otimes$ for multiplication/tensor product, $\sum$ for aggregation) appear directly on lines or at intersections.

**Arrowhead styles**

- **Single-head (→):** Default for unidirectional flow
- **Double-head (↔):** Bidirectional relationships (e.g., protein-protein interaction)
- **T-bar (⊣):** Inhibition in signaling pathways
- **Open circle (○):** Weak or stochastic influence

### D. Typography & Icons

**Design Philosophy:** Maintain clear distinction between module identification and mathematical notation.

**Typography**

- **Labels (Module Names, Process Steps):** Sans-Serif typefaces (Arial, Roboto, Helvetica, Source Sans, Inter)
  - Bold for headers and stage names; regular weight for descriptive text
  - All-caps discouraged except for acronyms (DNA, CRISPR, fMRI)
- **Variables (Mathematical):** Serif typefaces (Times New Roman, Computer Modern, LaTeX defaults)
  - Variables (e.g., $x$, $\theta$, $\mathcal{L}$) must appear in serif italic
  - Numeric constants and operators remain upright
- **Captions and annotations:** Smaller sans-serif, regular weight, lighter gray color (60-70% of body text opacity) to recede visually

**Iconography Options**

Icons are optional decorative elements, not meaning-bearing tokens. When used, they should reinforce a label, not replace it.

- **Process / Workflow:**
  - Magnifying glass 🔍 — inspection, analysis, QC
  - Gear ⚙️ — processing, transformation
  - Flask 🧪 — experimental step
  - Chart 📊 — statistical analysis
- **Data / Content:**
  - Document 📄 — reference, paper, text data
  - Image 🖼️ — image data (prefer a visual thumbnail over a generic icon when possible)
  - Database 🗄️ — stored dataset
- **State / Status:**
  - Checkmark ✓ — validated, passed
  - Warning ⚠️ — caveat, limitation
  - Clock ⏱️ — time-sensitive, longitudinal
- **Domain-Specific (biomedical):**
  - Brain 🧠 — nervous system (use sparingly; too-cute in formal contexts)
  - Heart ❤ — cardiovascular
  - DNA helix 🧬 — genetics, molecular biology
  - Microscope 🔬 — imaging, microscopy
  - Pill 💊 — pharmacology, treatment

Common choices include: limit icons to 3-5 per diagram; use consistent size (~24px at 1080p); always pair an icon with a text label.

---

## 3. Common Pitfalls

The following patterns are reused verbatim from PaperBanana's `neurips2025_diagram_style_guide.md` (Apache-2.0). They apply to any scientific presentation regardless of discipline.

- ❌ **The "PowerPoint Default" Look:** Standard blue/orange presets with prominent black borders. Immediately identifies a slide as default-styled and unfinished.
- ❌ **Font Mixing:** Applying serif fonts to module labels creates dated impressions. Serif is reserved for math variables and body text in formal reports.
- ❌ **Inconsistent Dimensionality:** Random mixing of 2D and 3D without intentional logic. Pick one convention (2D for matrices, 3D for tensors) and apply it uniformly.
- ❌ **Primary Backgrounds:** Saturated yellow or blue grouping containers distract from content. Use pale pastels (the Zone Strategy) instead.
- ❌ **Ambiguous Arrows:** Identical line styles for different flow types confuse readers. If your diagram has forward flow, feedback loops, and inhibition, give each a distinct line style.
- ❌ **Legend Reliance:** A diagram that can't be read without its legend is failing. Prefer direct labeling.
- ❌ **Decorative Noise:** Drop shadows, gradients, bevels, and other "polish" effects make a diagram look dated. Flat design with purposeful color is the modern standard.

---

## 4. Domain-Specific Styles for Biomedical Research

### Clinical / Translational research

- **Character:** Formal, patient-centered, trust-building, rigorous.
- **Elements:** CONSORT-style flow diagrams (rounded rectangles with patient counts), Kaplan-Meier curves, forest plots, patient avatars or stick figures, anatomical silhouettes, hazard ratio visualizations, subgroup analysis trees.
- **Color tendencies:** Restrained palette dominated by pale blue (clean, clinical) and soft gray. Accent colors reserved for treatment arms (typically blue vs. orange) and significance markers (red for p<0.05, desaturated for non-significant).
- **Layout preference:** Linear left-to-right flow for trial timelines; top-to-bottom for patient flow (enrollment → randomization → follow-up → analysis). Use the Macro-Micro pattern to zoom into specific cohort subsets.
- **Typography:** Sans-serif labels for all stage names; consistent patient-count formatting ("n = 245"); bold for the primary outcome variable.

### Wet-lab / Bench science

- **Character:** Mechanism-focused, pathway-oriented, hands-on, detailed.
- **Elements:** Signaling pathway diagrams with curved arrows for activation/inhibition, experimental protocol flowcharts (rounded rectangles for steps, diamonds for decision points), gel/blot representations, molecular structure renderings, cell cartoons (nucleus, cytoplasm, membrane), plasmid maps.
- **Color tendencies:** Warmer palette (cream backgrounds work well), with distinct colors for protein families or molecular types. Traffic-light metaphor (green=activation, red=inhibition) is well-understood in this domain.
- **Layout preference:** Pathway diagrams are typically top-to-bottom or follow the biological flow (upstream → downstream). Experimental protocols are left-to-right.
- **Special conventions:** Arrowheads mean activation (→); T-bars mean inhibition (⊣); dashed lines mean hypothesized or speculative connections.

### Neuroscience / Imaging

- **Character:** Spatially-grounded, anatomically-accurate (when possible), signal-oriented.
- **Elements:** Brain silhouettes (sagittal, coronal, or dorsal views), circuit diagrams with node-and-edge representations, electrophysiology traces, calcium imaging heatmaps, behavioral paradigm timelines, raster plots, anatomical atlases.
- **Color tendencies:** Pale blue or pale lavender for background (mimics brain atlas aesthetics). Perceptually-uniform colormaps (viridis, magma, plasma) for heatmaps and activation maps — NEVER jet/rainbow (see `paperbanana-plot-style-distilled.md` for the full rationale).
- **Layout preference:** Circuit diagrams often use grouped regions (cortex, subcortex, brainstem) with curved arrows for projections. Behavioral paradigms use left-to-right timelines with event markers.
- **Special conventions:** Brain regions are labeled directly on the silhouette, not in a legend. Time scales on electrophysiology traces are shown with explicit scale bars (e.g., "100 μV | 50 ms"), not axes.

### Computational / Modeling

- **Character:** Minimalist, abstract, textbook-like, precision-oriented.
- **Elements:** Graph networks (nodes and edges), phase diagrams, simulation flowcharts, equation blocks embedded in the diagram, loss landscapes, parameter sweep visualizations, convergence plots.
- **Color tendencies:** Restrained — mostly grayscale or monochrome with one highlight color (gold, deep blue, or muted red) for the key variable. Busy colors distract from mathematical clarity.
- **Layout preference:** Equations are typeset in-line or as blocks; diagrams are simple node-edge graphs with clear topology. Use the Softened Geometry principle but lean toward the minimalist end.
- **Typography:** Math variables in serif italic are non-negotiable. Module labels can use the same sans-serif as other domains but may also use LaTeX-style monospaced labels for variables that appear both in diagrams and in equations.

---

## 5. Applying this guidance to Debrief's diagram libraries

Debrief's `style_config.json.constraints.permitted_diagram_types` allows a subset of three diagram libraries: **Mermaid**, **rough.js**, and **inline SVG**. This section gives concrete guidance for applying the Section 2 style options to each library.

### Mermaid

Mermaid diagrams should be themed via the `%%{init}%%` directive at the top of every Mermaid block to apply the project's color palette. The Slide Maker should set `themeVariables` with the primary, secondary, and background colors from `style_config.json`. Example pattern (not a verbatim snippet — the Slide Maker composes this):

```
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor': '<primary from style_config>',
  'primaryTextColor': '<text from style_config>',
  'lineColor': '<neutral from style_config>',
  'secondaryColor': '<secondary from style_config>',
  'tertiaryColor': '<background from style_config>'
}}}%%
```

**Shape mapping:** Use rounded-corner shapes (`([...])` for rounded rectangles, `((...))` for circles) for process nodes; use square brackets (`[...]`) for data nodes. This matches the Softened Geometry principle.

**Arrow mapping:** Use `-->` for forward flow (solid), `-.->` for dashed (feedback/optional), and label arrows directly with `-->|activation|` for semantic clarity.

### rough.js

rough.js produces hand-drawn sketchy diagrams. Use it sparingly and only for projects where the informal aesthetic is appropriate (lab meetings, working hypotheses, exploratory analysis). Do NOT use it for formal publications or clinical trial documents.

**Parameter guidance:**
- `roughness`: 0.5-1.5 (lower = cleaner; higher = more sketchy)
- `bowing`: 1-2 (how much lines curve)
- `fillStyle`: `hachure` or `cross-hatch` for scientific illustration
- `strokeWidth`: 1-2 for fine details, 2-3 for structural elements
- `stroke`: use the project's text/line color from `style_config.json`
- `fill`: use the project's pastel palette colors from the Zone Strategy

### inline SVG

Inline SVG gives the most control and should be used for precise anatomical illustrations, circuit diagrams, or custom layouts that Mermaid/rough.js cannot produce.

**Guidance:**
- Set `font-family` on text elements to match the project's typography (sans-serif for labels, serif-italic for math).
- Use the project's color palette via CSS custom properties (`var(--color-primary)`, `var(--color-accent)`) rather than hardcoded hex codes. This lets the style compiler re-theme diagrams without rewriting SVG.
- Use `rx="8" ry="8"` on `<rect>` elements to enforce rounded corners per Softened Geometry.
- Use `<marker>` elements for consistent arrowheads across the deck.
- Keep SVG file size reasonable — strip out editor metadata (Inkscape, Illustrator) before embedding.
- For biomedical silhouettes (brain, anatomy), prefer simplified outline SVGs over detailed illustrations. The goal is recognition, not realism.

---

*This file is loaded by the Debrief Stylist agent as a craft-knowledge baseline per Section 22.8 and REQ-STYLE-2 step 2. It is adapted from PaperBanana (https://github.com/dwzhu-pku/PaperBanana), © 2026 Google LLC, Apache License 2.0. See `${CLAUDE_PLUGIN_ROOT}/NOTICE` for attribution details and the patent disclosure.*
