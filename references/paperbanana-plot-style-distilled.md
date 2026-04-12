# Scientific Plot Style Guide (PaperBanana-Distilled)

```
NOTICE
=====================================================================
This document is adapted from PaperBanana
(https://github.com/dwzhu-pku/PaperBanana),
© 2026 Google LLC, licensed under Apache License 2.0.

Source file:   style_guides/neurips2025_plot_style_guide.md
Source commit: main branch as of 2026-04-11 (specific commit hash to
                be recorded in references/VERSIONS.md when the plugin
                is first packaged for release)

Modifications (Apache-2.0 §4(b)):

- Retargeted the audience framing from NeurIPS 2025 ML/AI paper authors
  to biomedical/neuroscience researchers giving lab meetings, seminars,
  conference talks, and journal clubs.
- Added a NEW Section 4 "Biomedical-Specific Plot Types" (between the
  upstream's general chart types in Section 3 and its "Common Pitfalls"
  section). Covers 8 plot types common in biomedical research:
  Kaplan-Meier survival curves, forest plots, volcano plots, gene
  expression heatmaps, Manhattan plots (GWAS), ROC / precision-recall
  curves, dose-response curves, and box plots of patient cohorts.
- Added a NEW Section 6 "Applying this guidance in Debrief" that
  clarifies how plots are produced in Debrief (NOT via matplotlib or
  plotly — Debrief embeds pre-rendered images, hand-authors simple
  inline SVG, or uses Mermaid pie/gantt). Includes an explicit rule
  against proposing matplotlib/plotly/seaborn as diagram libraries.
- Dropped upstream's implicit matplotlib syntax (rcParams, figsize,
  alpha, linewidth) since Debrief does not call matplotlib. Aesthetic
  guidance retained; code-specific hooks removed.
- Retained VERBATIM (marked inline below): the aesthetic principles in
  Section 1 (precision + accessibility + high contrast), the colormap
  rules (viridis/magma/plasma as standards, coolwarm for diverging,
  NO jet/rainbow), the axes/grids/spines conventions, the legend
  placement options, the direct-labeling preference, all 7 upstream
  Type-Specific Guidelines (Bar, Line, Tree/Pie, Scatter, Heatmap,
  Radar, Miscellaneous), and the entire Section 5 "Common Pitfalls"
  list.

Modified by:        Carlo Fusco and Leonardo Restivo
Modification date:  2026-04-11
License:            Apache-2.0 (inherited)

PATENT NOTICE — The PaperBanana README states that patents have been
filed by Google covering the multi-agent pipeline workflows. This file
reuses ONLY documentation content (data-viz style guidance), not the
multi-agent architecture. See ${CLAUDE_PLUGIN_ROOT}/NOTICE for the
full patent disclosure.

The upstream file is available at:
https://github.com/dwzhu-pku/PaperBanana/blob/main/style_guides/neurips2025_plot_style_guide.md
=====================================================================
```

---

## Purpose

This file is **craft-knowledge baseline** for data-visualization aesthetics in scientific presentations. It is loaded by:

- The Debrief **Stylist** agent during every Phase 2 style dialog (per Section 22.8 Stylist row "Always Loaded" column and REQ-STYLE-2 step 2). The Stylist uses this file to propose data-visualization conventions in the project's `style_guide.md`.
- The **visual-qa agent** at Tier 2 judgment time (via `slide-qa-checklist.md` which references this file). The visual-qa agent uses these conventions to flag embedded plot images that violate standards (e.g., jet colormap usage → Tier 2 warning).

**Sibling files in `${CLAUDE_PLUGIN_ROOT}/references/`:**
- `paperbanana-diagram-style-distilled.md` — diagram aesthetics (the diagrams counterpart to this file)
- `ai4vis-survey-distilled.md` — academic grounding in visualization design principles (arXiv:2102.01330)
- `slide-qa-checklist.md` — the visual-qa rubric that operationalizes these principles as evaluation criteria
- `paperbanana-derivation-meta-prompt.md` — meta-prompt used only in reference-derivation mode

---

## 1. The Scientific Plot Look

The aesthetic standard this guide codifies is defined by **precision, accessibility, and high contrast**. The "default" academic look has shifted away from bare-bones styling toward a more graphic, publication-ready presentation.

- **Vibe:** Professional, clean, information-dense.
- **Backgrounds:** There is a heavy bias toward **stark white backgrounds** for maximum contrast in print and PDF reading, though the "Seaborn-style" light-gray background remains an accepted variant.
- **Accessibility:** A strong emphasis on distinguishing data not just by color, but by **texture (patterns) and shape (markers)** to support black-and-white printing and colorblind readers. Plots that rely exclusively on color encoding fail the accessibility test.

---

## 2. Detailed Style Options

### Color Palettes

**Categorical Data**

- **Soft Pastels:** Matte, low-saturation colors (salmon, sky blue, mint, lavender) are frequently used to prevent visual fatigue in multi-series plots.
- **Muted Earth Tones:** "Academic" palettes using olive, beige, slate gray, and navy. Well-suited for formal clinical presentations.
- **High-Contrast Primaries:** Used sparingly when categories must be distinct (e.g., deep orange vs. vivid purple for treatment vs. control).
- **Accessibility Mode:** A growing convention involves combining color with **geometric patterns** (hatches, dots, stripes) to differentiate categories, so the plot remains readable in black-and-white and for colorblind viewers.

**Sequential Data & Heatmaps**

- **Perceptually Uniform:** **Viridis** (blue-to-yellow) and **Magma / Plasma** (purple-to-orange) are the standard. These colormaps preserve perceptual distance — a value change from 0.5 to 0.6 looks similar in magnitude to a change from 0.1 to 0.2.
- **Diverging:** **Coolwarm** (blue-to-red) is used for values that have a meaningful midpoint (e.g., log2 fold change, z-score). The midpoint is typically white or pale gray.

**AVOID: Jet / Rainbow colormap.** The traditional jet/rainbow colormap is perceptually nonuniform and misleads readers about magnitude. It is almost entirely absent from modern scientific publications. The visual-qa agent should flag any embedded heatmap using jet as a Tier 2 warning. This rule is preserved verbatim from the upstream PaperBanana guide and reinforced by the AI4VIS survey (see `ai4vis-survey-distilled.md` for the academic grounding).

### Axes & Grids

**Grid Style**

- **Visibility:** Grid lines are rarely solid. Common choices include **fine dashed (`--`)** or **dotted (`:`)** lines in light gray.
- **Placement:** Grids are consistently rendered **behind** data elements (low Z-order). Data should always visually pop above the grid, not be overrun by it.

**Spines (Borders)**

- **The "Boxed" Look:** A full enclosure (black spines on all 4 sides) — common in formal/clinical contexts.
- **The "Open" Look:** Removing the top and right spines for a minimalist appearance — common in modern publications and presentation decks.

Both are accepted; pick one and apply it consistently across all plots in the deck.

**Ticks**

- Ticks are generally subtle, facing inward, or removed entirely in favor of grid alignment.
- Tick labels should be horizontal when possible; rotate 45° only when necessary to prevent overlap.

### Layout & Typography

**Typography**

- **Font Family:** Exclusively **Sans-Serif** (Helvetica, Arial, DejaVu Sans, Source Sans, Inter). Serif fonts are rarely used for plot labels and immediately signal a dated aesthetic.
- **Label Rotation:** X-axis labels rotated 45° only when necessary; horizontal by default.
- **Font sizes:** Consistent across all plots in the deck — typically axis labels ≥ body text size (to remain readable in projection); tick labels slightly smaller than axis labels; legend text matching axis-label size.

**Legends**

Two well-accepted placements:

- **Internal Placement:** Floating the legend inside the plot area (top-left or top-right) to maximize the "data-ink ratio." Best when the plot has empty regions in corners.
- **Top Horizontal:** Placing the legend in a single row above the plot title. Best for plots with many categories (≥5) where internal placement would crowd the data.

**Annotations**

- **Direct Labeling:** Instead of forcing readers to reference a legend, text is often placed directly next to lines or on top of bars. Direct labeling reduces cognitive load and is especially effective for 2-4 series.

---

## 3. Type-Specific Guidelines (General Chart Types)

### Bar Charts & Histograms

- **Borders:** Two distinct styles are accepted:
  - **High-Definition:** Using **black outlines** around colored bars for a "comic-book" or high-contrast look.
  - **Borderless:** Solid color fills with no outline (often used with light gray backgrounds).
- **Grouping:** Bars are grouped tightly, with significant whitespace between categorical groups.
- **Error Bars:** Consistently styled with **black, flat caps**. No oversized or decorative caps. Caps should be small relative to the error bar length.

### Line Charts

- **Markers:** A critical observation — lines almost always include **geometric markers** (circles, squares, diamonds, triangles) at data points, rather than being smooth strokes alone. Markers help readers identify discrete measurements.
- **Line Styles:** Use **dashed lines** (`--`) for theoretical limits, baselines, or secondary data. **Solid lines** for primary experimental data.
- **Uncertainty:** Represented by semi-transparent **shaded bands** (confidence intervals, SEM) rather than simple vertical error bars at each point. Shaded bands read more continuously.

### Tree & Pie / Donut Charts

- **Separators:** Thick **white borders** are standard to separate slices or treemap blocks.
- **Structure:** Thick **Donut charts** are preferred over traditional pie charts. Donuts leave space in the center for a summary statistic (total, percentage, headline number).
- **Emphasis:** "Exploding" (detaching) a specific slice is a common technique to highlight a key statistic.
- **Pie/donut limits:** Use only when there are ≤5 categories. Beyond 5, switch to a bar chart — pie charts are perceptually harder to read at higher category counts.

### Scatter Plots

- **Shape Coding:** Use different marker shapes (circles, triangles, squares, diamonds) to encode a categorical dimension alongside color. This is the accessibility path — plots remain readable in black and white.
- **Fills:** Markers are typically solid and fully opaque for small datasets; semi-transparent (alpha ~0.5) for dense overlapping data where individual points matter less than the density.
- **3D Plots:** Depth is emphasized by drawing "walls" with grids or using drop-lines to the "floor" of the plot. 3D scatter plots are controversial — prefer 2D projections or paired 2D subplots when possible.

### Heatmaps

- **Aspect Ratio:** Cells are almost strictly **square**. Non-square cells distort perception.
- **Annotation:** Writing the exact value (in white or black text) **inside the cell** is highly preferred over relying solely on a color bar. In-cell annotation makes the plot self-contained.
- **Borders:** Cells are often borderless (smooth gradient look) or separated by very thin **white** lines. Avoid black cell borders — they compete with the data.
- **Colormap:** Viridis or magma for sequential; coolwarm for diverging. Never jet.

### Radar Charts

- **Fills:** The polygon area uses **translucent fills** (alpha ~0.2) to show grid lines underneath and to prevent overlapping polygons from obscuring each other.
- **Perimeter:** The outer boundary is marked by a solid, darker line.
- **Use sparingly:** Radar charts are hard to read for more than 3 series. Prefer small-multiples of bar charts for higher-dimensional comparisons.

### Miscellaneous

- **Dot Plots / Lollipops:** Used as a modern alternative to bar charts. Styled as "lollipops" (dots connected to the axis by a thin line). Cleaner than bars for sparse data, and readers' eyes track the dot position rather than the bar height.

---

## 4. Biomedical-Specific Plot Types (New in Debrief's distillation)

This section is Debrief-specific — not in the upstream PaperBanana file. Biomedical researchers encounter plot types that are rare or absent in ML/AI papers but ubiquitous in clinical research, genomics, pharmacology, and neuroscience. This section documents the visual conventions for 8 common biomedical plot types.

### Kaplan-Meier Survival Curves

- **Structure:** Step function with horizontal segments at each survival probability; vertical drops at each event time.
- **Confidence bands:** Shaded 95% CI bands around each curve, semi-transparent (alpha ~0.2).
- **Censoring:** Small vertical tick marks on the curve at censored observation times (critical — a KM plot without censoring ticks is incomplete).
- **At-risk table:** A small table below the x-axis showing the number of subjects at risk per group at each major time point (e.g., every 6 or 12 months). The at-risk table is expected at publication quality.
- **Colors:** Typically 2-3 colors for treatment arms. Traffic-light avoidance: do NOT use red vs. green (colorblind inaccessibility) — prefer blue vs. orange or other accessible pairs.
- **Annotations:** Log-rank test p-value displayed in a corner; hazard ratio with 95% CI optionally labeled.
- **Axis:** X-axis typically time (months or years); y-axis probability 0-1 (or 0-100%).

### Forest Plots

- **Layout:** Horizontal. Each study or subgroup occupies one row.
- **Point estimates:** Squares or diamonds, sized proportionally to study weight (inverse variance).
- **Error bars:** Horizontal lines for 95% CI.
- **Reference line:** Vertical line at the null effect (1.0 for ratios, 0.0 for differences).
- **Summary:** A diamond at the bottom showing the pooled estimate with its 95% CI; diamond width represents CI width.
- **Subgroups:** Grouped with whitespace between groups; subgroup summaries as smaller diamonds.
- **Heterogeneity annotation:** I² statistic displayed near the summary diamond.
- **Colors:** Typically monochrome (black or dark gray) to emphasize the statistical message; color only for highlighting subgroups.

### Volcano Plots

- **Axes:** X-axis: log2 fold change. Y-axis: −log10(p-value).
- **Point coloring:** Gray for non-significant (|log2FC| below threshold OR p > threshold); red/orange for significantly up-regulated (positive log2FC, low p); blue or purple for significantly down-regulated (negative log2FC, low p).
- **Thresholds:** Horizontal line at significance threshold (−log10(0.05) ≈ 1.3; often more stringent at 0.01 or after multiple-testing correction). Vertical lines at fold-change thresholds (typically ±1 or ±2 on log2 scale).
- **Labels:** Top N hits labeled with gene/feature names. Avoid labeling every significant point — pick the most meaningful.
- **Use perceptually sensible colors** (not rainbow). Maintain colorblind accessibility via shape or label, not color alone.

### Gene Expression Heatmaps

- **Rows:** Genes (features). Often many (100-1000+); row labels usually hidden when too dense.
- **Columns:** Samples or conditions. Column labels often visible.
- **Dendrograms:** Optional hierarchical clustering dendrograms on rows and/or columns. Use when the clustering structure is itself informative.
- **Colormap:** Viridis or diverging (coolwarm) depending on whether values are unsigned (expression levels) or signed (log fold change, z-score). NEVER jet.
- **Normalization:** The normalization method (z-score per row, log-transform, quantile normalization) MUST be stated in the caption or legend.
- **In-cell annotations:** Rarely used for expression heatmaps because there are too many cells. Use a color bar legend instead, with tick marks at the extremes and midpoint.
- **Row/column gaps:** Thin gaps or no gaps. Thick borders would clutter the display.

### Manhattan Plots (GWAS)

- **X-axis:** Chromosomes in order, typically colored in alternating shades (light gray / dark gray or two pale colors) to help readers distinguish chromosome boundaries.
- **Y-axis:** −log10(p-value).
- **Threshold lines:**
  - Horizontal line at **genome-wide significance** (typically p = 5×10⁻⁸, i.e., y = 7.3).
  - Horizontal line at **suggestive significance** (typically p = 1×10⁻⁵, i.e., y = 5).
- **Point density:** High. Dots are small (~1-2 pixels at typical resolution) and opaque.
- **Labels:** Top hits labeled with SNP rs-IDs or gene names. Leader lines when needed to avoid overlap.
- **Colors:** Typically 2-color alternation between chromosomes. Highlight hits in a third color (red or orange).

### ROC Curves / Precision-Recall Curves

- **ROC axes:** X = false positive rate (1 - specificity); Y = true positive rate (sensitivity). Both 0-1.
- **PR axes:** X = recall; Y = precision. Both 0-1.
- **Reference line:** Diagonal from (0,0) to (1,1) for ROC (represents random classifier). PR plots use a horizontal line at the baseline positive rate.
- **Area Under Curve (AUC):** Displayed in the legend alongside each curve: `Model A (AUC = 0.87)`. Include confidence interval if possible.
- **Style:** Solid lines, no markers (too many data points — the curve should be smooth). Use shaded bands for confidence intervals when comparing models.
- **Colors:** Distinct color per model; avoid using the same color for related variants.

### Dose-Response Curves

- **X-axis:** Concentration, typically log-scale (log10 or log2). Label axes clearly with units.
- **Y-axis:** Response (e.g., % of maximum, viability, binding).
- **Fit:** Typically a sigmoidal curve (Hill equation, four-parameter logistic). Show the fit as a solid line; show the data points as markers with error bars.
- **EC50 / IC50 annotation:** The half-maximal effective concentration annotated on the plot as a vertical dashed line or a direct label.
- **Error bars:** SEM or SD on y values; include a note in the caption explaining which.
- **Compare conditions:** Multiple conditions (compound A vs. B, wildtype vs. mutant) as different-colored curves with markers. Use the shape-coding accessibility rule — don't rely on color alone.

### Box Plots of Patient Cohorts

- **Structure:** One box per group; whiskers extending to 1.5×IQR (Tukey convention) OR to min/max; outliers as individual points.
- **Scatter overlay:** CRITICAL for small n (< 50 per group) — overlay individual data points as a scatter (jittered) on top of the box. A box plot of n=5 without scatter points is misleading.
- **Notches:** Optional; notches roughly indicate 95% CI of the median and enable visual significance testing (non-overlapping notches suggest significantly different medians).
- **Whisker convention:** MUST be stated in the caption (1.5×IQR vs. min/max). Different conventions make plots non-comparable.
- **Colors:** Muted tones; one color per group. Avoid red/green pairings.
- **Significance annotations:** P-values annotated with brackets and asterisk notation (n.s., *, **, ***). Use a single convention throughout the deck.

---

## 5. Common Pitfalls (What to Avoid)

The following patterns are reused verbatim from PaperBanana's `neurips2025_plot_style_guide.md` (Apache-2.0). They apply to any scientific plot regardless of discipline.

- ❌ **The "Excel Default" Look:** Avoid heavy 3D effects on bars, shadow drops, serif fonts (Times New Roman) on axes, and rainbow colors. The default Excel aesthetic immediately signals an unfinished or unprofessional plot.
- ❌ **The "Rainbow" Map:** Avoid the jet / rainbow colormap; it is considered outdated and perceptually misleading. The visual-qa agent should flag this as a Tier 2 warning on any embedded heatmap.
- ❌ **Ambiguous Lines:** A line chart without markers can look ambiguous if data points are sparse; always add markers at data points so readers can distinguish measurements from interpolation.
- ❌ **Over-reliance on Color:** Failing to use patterns or shapes to distinguish groups makes the plot inaccessible to colorblind readers and to anyone reading a black-and-white printout. Use shape coding on scatter plots, patterns on bar charts, and dashed/solid distinctions on line plots.
- ❌ **Cluttered Grids:** Avoid solid black grid lines; they compete with the data. Always use light-gray dashed or dotted grids, placed behind data (low Z-order).

---

## 6. Applying this guidance in Debrief (Debrief-specific, not from upstream)

**Critical constraint:** Debrief does **NOT** generate plots from raw data. The Slide Maker does not call matplotlib, plotly, seaborn, bokeh, or any Python/JavaScript plotting backend. Plots appear in Debrief slides in exactly **three** ways:

### 6.1 Embedded images (most common)

Pre-rendered figures from:
- `assets/reference/papers/<paper_slug>/figures/fig_*.png` — figures extracted by the paper analyzer from imported journal-club PDFs (REQ-CONSULT-17)
- `assets/images/` — user-provided images (photographs, schematic drawings, pre-rendered plots from other tools like GraphPad, Prism, R)
- `assets/reference/slides/` — reference slides from imported decks (PPTX, PDF, HTML)

The Slide Maker embeds these verbatim in slides. The Slide Maker does not edit, re-render, or re-style them. The **visual-qa agent** applies this guide's principles to evaluate them:

- Tier 2 warning: the embedded plot uses jet / rainbow colormap
- Tier 2 warning: the embedded plot has ambiguous lines (no markers)
- Tier 2 warning: the embedded plot has heavy Excel-default styling
- Tier 2 warning: the embedded plot relies on color alone (no shape/pattern coding)

These warnings are surfaced at gate G3.3 so the user can decide whether to accept or request a better figure from the original source.

### 6.2 Inline SVG chart-like visualizations

The Slide Maker MAY hand-author simple SVG plots for slides — for example, a 3-bar comparison, a simple line chart, a schematic survival curve, a conceptual dose-response. These should:

- Follow the **color palette** from `style_config.json` (use CSS custom properties, not hardcoded hex).
- Follow the **axes/grids/spines** conventions from Section 2 (light gray dashed grid behind data, open or boxed spines).
- Follow the **typography** rules (sans-serif, horizontal labels, legend placement).
- Use the **type-specific guidelines** from Section 3 for general chart types or Section 4 for biomedical-specific types.

Inline SVG chart-like visualizations are **schematic, not data-driven**. They communicate a pattern or idea, not a specific dataset. For real data-driven plots, the user should render them externally and embed as images (Section 6.1).

### 6.3 Mermaid pie and gantt charts

Mermaid supports two chart types relevant for slides: `pie` (pie / donut charts) and `gantt` (project timelines, experimental protocols). For these:

- Use `%%{init}%% themeVariables` to apply the project's color palette (same pattern as diagram Mermaid per `paperbanana-diagram-style-distilled.md` Section 5).
- Follow Section 3's guidance on pie/donut charts (≤5 categories, thick white separators, prefer donut over pie).

Mermaid does NOT support line charts, scatter plots, bar charts, heatmaps, or any other chart type relevant for scientific data. Do not attempt to use Mermaid for these.

### 6.4 Explicit rule: no matplotlib/plotly/seaborn proposals

The Stylist, the visual-qa agent, and the Blueprint Author MUST NOT propose adding matplotlib, plotly, seaborn, bokeh, altair, or any Python/JavaScript plotting backend to Debrief. Debrief's permitted diagram libraries per `style_config.json.constraints.permitted_diagram_types` are **Mermaid, rough.js, and inline SVG** only. Proposing matplotlib would require adding a Python plotting stack to the conda environment, a subprocess invocation mechanism, and a way to surface rendered images back into the slide pipeline — none of which exist, and all of which would require a major spec change.

When the user needs a data-driven plot, they render it in their preferred external tool (Prism, GraphPad, R, Python, Excel) and provide the rendered image via `assets/images/`. Debrief embeds it. That is the only supported workflow for data-driven plots.

---

*This file is loaded by the Debrief Stylist and visual-qa agents as a craft-knowledge baseline per Section 22.8 and Section 24.22. It is adapted from PaperBanana (https://github.com/dwzhu-pku/PaperBanana), © 2026 Google LLC, Apache License 2.0. See `${CLAUDE_PLUGIN_ROOT}/NOTICE` for attribution details and the patent disclosure.*
