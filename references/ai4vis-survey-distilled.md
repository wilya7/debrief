# AI4VIS Survey — Distilled Reference

```
CITATION
=====================================================================
This document distills concepts and principles from:

  Wu, A., Wang, Y., Shu, X., Moritz, D., Cui, W., Zhang, H., Zhang, D.,
  and Qu, H. "AI4VIS: Survey on Artificial Intelligence Approaches for
  Data Visualization." IEEE Transactions on Visualization and Computer
  Graphics, 2021. arXiv:2102.01330.
  https://arxiv.org/abs/2102.01330

Used under academic fair use for the purpose of documenting design
principles in a derivative software system (Debrief). This document
PARAPHRASES rather than reproduces the paper's text, with a small
number of direct quotes (each ≤3 sentences) clearly delimited and
attributed inline. For authoritative statements, consult the original
paper.

This document is NOT an Apache-2.0 derivative. It is a fair-use
academic distillation, distinct from the PaperBanana-derived files
in this directory (`paperbanana-diagram-style-distilled.md`,
`paperbanana-plot-style-distilled.md`, `paperbanana-derivation-meta-prompt.md`,
`slide-qa-checklist.md`), which ARE Apache-2.0 derivatives.

Distilled by:       Carlo Fusco and Leonardo Restivo
Distillation date:  2026-04-11
Attribution regime: Primary Literature (fair-use academic citation)

BibTeX entry:

@article{wu2021ai4vis,
  title={AI4VIS: Survey on Artificial Intelligence Approaches
         for Data Visualization},
  author={Wu, Aoyu and Wang, Yun and Shu, Xinhuan and Moritz, Dominik and
          Cui, Weiwei and Zhang, Haidong and Zhang, Dongmei and Qu, Huamin},
  journal={IEEE Transactions on Visualization and Computer Graphics},
  year={2021},
  note={arXiv:2102.01330},
  url={https://arxiv.org/abs/2102.01330}
}
=====================================================================
```

---

## Purpose

This file provides **academic grounding** for visualization design decisions in the Debrief pipeline. Unlike the sibling files in `${CLAUDE_PLUGIN_ROOT}/references/` that are **prescriptive style guides** (telling the Stylist what to do), this file is **descriptive and foundational** — it tells the Stylist and visual-qa agent *why* the prescriptive rules exist and gives them authoritative sources to cite when users ask.

**Loaded by:** The **Stylist** agent (always, per Section 22.8 "Always Loaded" column and REQ-STYLE-2 step 2). Secondary consumer: the **visual-qa agent** may consult it indirectly when explaining why a Tier 2 warning was triggered.

**Sibling files:**
- `paperbanana-diagram-style-distilled.md` — prescriptive diagram aesthetics (what to do)
- `paperbanana-plot-style-distilled.md` — prescriptive data-viz aesthetics (what to do)
- `slide-qa-checklist.md` — the visual-qa agent's 4-dimensional evaluation rubric
- `paperbanana-derivation-meta-prompt.md` — the Stylist's reference-derivation instructions

This file is the only one in the set that carries **fair-use academic citation** as its attribution regime. The four sibling files above are Apache-2.0 derivatives of PaperBanana; this one is a paraphrase of a copyrighted IEEE TVCG paper.

---

## 1. Why This File Exists

The Stylist's other bundled references tell it *what* to do: rounded-rectangle process nodes, viridis colormaps, sans-serif labels, tight bar grouping, etc. They are prescriptive craft knowledge distilled from PaperBanana's NeurIPS 2025 style guides.

This file tells the Stylist *why* those rules exist. When a user asks "why should I use viridis instead of jet?" or "why should this bar chart use equal-sized bars?", the Stylist needs authoritative sources to cite. Bare assertions ("because viridis is better") are unconvincing; citations to foundational visualization literature ("because Cleveland and McGill (1984) showed that perceptually uniform colormaps preserve quantitative accuracy where rainbow colormaps do not") are persuasive.

The visual-qa agent also benefits: when it flags a Tier 2 warning about "amateurish styling" or "ambiguous lines", it can cite AI4VIS (Wu et al. 2021) and the foundational references the survey highlights, rather than just asserting that a pattern is bad.

**This file is citation ammunition, not a style rulebook.** For the rulebook, read the sibling files.

---

## 2. Core Thesis

The AI4VIS survey's organizing argument is that visualizations have become a data format in their own right — comparable to text, image, and audio — and can be processed, analyzed, generated, and improved using AI techniques. From the paper:

> "Visualizations themselves have become a data format" (Wu et al. 2021, arXiv:2102.01330, §1).

The survey organizes the field around a **WHAT / WHY / HOW** framework:

- **WHAT:** visualization data representations (chart images, program code, declarative specifications like Vega-Lite)
- **WHY:** the goals (generation, enhancement, analysis, recommendation)
- **HOW:** seven computational tasks (transformation, assessment, comparison, querying, reasoning, recommendation, mining)

**Why this framing matters for Debrief:** the Slide Maker produces slides as structured data (HTML files with typed content, embedded figures, math expressions, diagram markup). AI4VIS's premise — that these are processable visualization data, not end artifacts — applies directly to how Debrief thinks about slide generation. When the Stylist derives a style guide from a reference PPTX (per `paperbanana-derivation-meta-prompt.md`), it is treating the PPTX as visualization data to be analyzed, which is exactly the AI4VIS framing.

The survey also emphasizes that visualization interpretation is more sensitive than general image analysis:

> "A local change to a bar shape might significantly impact the encoded data and conveyed meanings" (Wu et al. 2021, §3).

The implication for Debrief: small style errors have outsize meaning-level consequences. A misplaced bar, an off-scale axis, or a mislabeled legend can mislead a reader about the underlying data — this is why the visual-qa Tier 2 checks matter.

---

## 3. The Cleveland & McGill Perceptual Hierarchy

The single most practically useful piece of content in the AI4VIS survey (for Debrief's purposes) is its emphasis on **Cleveland and McGill's 1984 perceptual ranking** of visual encoding channels. The survey treats this as definitive foundational work on how humans read charts.

Cleveland and McGill (1984) ranked visual encoding channels from most to least perceptually accurate for quantitative judgments:

1. **Position on a common scale** (e.g., dots on the same x-axis) — most accurate
2. **Position on non-aligned scales** (e.g., small multiples with independent axes)
3. **Length** (e.g., bar chart heights)
4. **Angle / slope** (e.g., pie chart slice angles, line chart trajectories)
5. **Area** (e.g., bubble chart marker sizes)
6. **Volume** (e.g., 3D bar heights)
7. **Color hue** (e.g., categorical color coding) — least accurate for quantitative judgment

### Debrief application

This hierarchy directly justifies several of the prescriptive rules in the sibling files:

- **Why bar charts beat pie charts for quantitative comparison:** bar charts encode values as length (rank 3), which humans read accurately. Pie charts encode values as angle (rank 4), which are harder to compare precisely. A bar chart of 5 categories is almost always easier to read than a pie chart of the same 5 categories. Cross-reference `paperbanana-plot-style-distilled.md` Section 3 on pie/donut chart preferences.

- **Why heatmaps should use perceptually uniform colormaps:** heatmaps encode values as color hue (rank 7 — the worst channel for quantitative judgment), so the colormap must preserve perceptual distance, or readers will misjudge the data. Viridis, magma, and plasma are engineered for perceptual uniformity. Jet and rainbow are NOT — they introduce artificial discontinuities and invert perceptual ordering in their brightness curves. Cross-reference `paperbanana-plot-style-distilled.md` Section 2.

- **Why in-cell annotation is preferred on heatmaps:** because color hue is perceptually unreliable, the exact value should be shown as text inside each cell. Readers can then use color as a quick-scan aid and text for the precise reading. Cross-reference `paperbanana-plot-style-distilled.md` Section 3 Heatmaps subsection.

- **Why direct labeling beats legend lookup:** direct labeling puts the label at the same position as the data (rank 1 — position on common scale), so the reader can associate label and value in a single glance. Legends force an eye-jump from data to legend and back, which adds cognitive load. Cross-reference `paperbanana-plot-style-distilled.md` Section 2 Layout & Typography.

Cleveland and McGill's ranking is the single most cite-worthy principle the Stylist has access to. When a user asks "why this encoding?", the answer often routes back to the hierarchy.

---

## 4. Mackinlay's APT Effectiveness Ranking

The AI4VIS survey also emphasizes **Mackinlay's A Presentation Tool (APT) system** (1986) as foundational. APT formalized the idea that visualizations can be ranked by effectiveness — specifically, by "accuracy rankings of quantitative perceptual tasks for different visual encoding channels" (paraphrase from Wu et al. 2021, §2). APT built on Cleveland and McGill's empirical ranking to construct an automated visualization-recommendation system.

The key insight from APT for Debrief: visualization design can be formalized. Not every design choice is arbitrary or taste-dependent — some choices are measurably better than others for specific tasks. The Stylist can ground its recommendations in this formalism: a bar chart is not "better" than a pie chart as a matter of opinion; it is measurably more accurate for quantitative comparison by Cleveland and McGill's criteria and Mackinlay's formalization.

The survey also highlights **Draco** (a more recent constraint-based design system) as a direct descendant of APT. Draco encodes visualization design rules as constraints over facts — essentially a formalized style guide that can validate a visualization against accepted best practices. Debrief's `style_guide.md` serves a similar role for slides: a project-specific constraint set that the Slide Maker conforms to.

---

## 5. Seven Dimensions of Visualization Quality

The AI4VIS survey identifies visualization quality as multi-faceted and context-dependent. It lists seven dimensions along which visualization quality can be measured:

1. **Informativeness** — how much useful information the visualization conveys
2. **Interestingness / saliency** — whether the visualization captures attention and highlights the important signal
3. **Accuracy of data representation** — whether the visualization faithfully represents the underlying data (cross-reference V-FAI-01 in `slide-qa-checklist.md`)
4. **Visual importance (human-perceived)** — how much a human weights different elements of the chart
5. **Complexity (appropriate to task)** — whether the visualization's information density matches the cognitive budget of the viewer
6. **Mobile-friendliness** — whether the visualization remains readable on small screens (context-dependent; not always relevant for presentation slides)
7. **Aesthetic appeal** — explicitly flagged by the survey as underexplored in AI4VIS research

### How these map to Debrief's visual-qa Tier 2 judgment

Debrief's 4-dimensional framework (Faithfulness / Conciseness / Readability / Aesthetics) from `slide-qa-checklist.md` partially maps to AI4VIS's 7 dimensions:

- **Faithfulness** (Debrief) ↔ **Accuracy of data representation** (AI4VIS)
- **Conciseness** (Debrief) ↔ **Complexity / informativeness** (AI4VIS)
- **Readability** (Debrief) ↔ **Visual importance** (AI4VIS) — both are about how easily a reader extracts the signal
- **Aesthetics** (Debrief) ↔ **Aesthetic appeal** (AI4VIS, underexplored)

The Debrief framework is narrower (4 dimensions vs. 7) because it drops dimensions that are less actionable for slide-level QA:
- **Informativeness** and **Interestingness** are handled upstream by the Consultant during the discovery dialog, not at slide-review time
- **Mobile-friendliness** is not a concern for Debrief's exported PDFs, which are rendered at a fixed 16:9 aspect ratio

### The aesthetic-neglect flag (direct quote)

> "Subjective metrics such as aesthetics are relatively underexplored, despite that they are considered important features of good visualizations" (Wu et al. 2021, §3).

This is a significant gap in the AI4VIS field. Debrief takes it seriously: the Stylist's craft-knowledge baseline (the three prescriptive PaperBanana-distilled files) is what fills the gap. Where AI4VIS-style research would say "we don't yet know how to measure aesthetic quality", Debrief uses the PaperBanana-derived distillation as a pragmatic operational answer.

---

## 6. Anti-Patterns Identified by the Survey

The AI4VIS survey identifies several patterns that distinguish high-quality visualization research/practice from low-quality. These are the survey's critiques — not Debrief-specific rules, but rather pitfalls the field recognizes.

### Unsystematic design

> "The design process is often unsystematic and lacks a strong methodological base" (Wu et al. 2021, §3, paraphrased).

Many visualizations are created ad hoc, without an explicit design rationale. The AI4VIS authors argue that formalizing design rules (as in Draco and APT) is an active area of research. **Debrief's approach:** the `style_guide.md` produced by the Stylist IS the explicit design rationale. The Consultant → Stylist → Slide Maker → visual-qa pipeline is a systematic alternative to ad hoc design.

### Aesthetic neglect

The survey flags aesthetics as underexplored (verbatim quote above). **Debrief's approach:** the three prescriptive craft-knowledge files (`paperbanana-diagram-style-distilled.md`, `paperbanana-plot-style-distilled.md`, `paperbanana-derivation-meta-prompt.md`) are Debrief's operational answer to this gap. They provide concrete style guidance distilled from community-accepted best practices.

### Perceptual mismatch between models and humans

> "Off-the-shelf CNNs were not currently a good model for human graphical perception" (Wu et al. 2021, §4, paraphrased).

The survey cites Haehn et al.'s work showing that general-purpose convolutional neural networks trained on natural images do not automatically learn to read charts the way humans do. **Debrief's approach:** the visual-qa agent is a Claude subagent (VLM), not a fine-tuned CNN. Claude's training includes significant exposure to scientific visualizations, diagrams, and charts, so it has closer-to-human graphical perception than a generic CNN. This is why Debrief uses a large VLM for Tier 2 judgment rather than a specialized plot-classifier.

### Visual clutter

The survey identifies visual clutter in line charts and scatterplots as a recognized problem and notes that layered overlays (e.g., semi-transparent confidence bands, fog-of-war dimming of non-focal series) help mitigate it. **Debrief's approach:** `paperbanana-plot-style-distilled.md` Section 3 Line Charts specifies semi-transparent shaded bands for uncertainty, direct labeling over legend lookup, and markers at data points to anchor the eye. All are clutter-reduction techniques.

### Bespoke chart-type failures

> "Deriving both encodings and data from bespoke, unknown chart types remains open" (Wu et al. 2021, §5, paraphrased).

Custom, non-standard visualizations are hard for automated pipelines to analyze. The AI4VIS pipelines work best on standard chart types (bar, line, scatter, heatmap). **Debrief's approach:** restrict the Slide Maker to well-established chart types (per `paperbanana-plot-style-distilled.md` Section 3) and the three permitted diagram libraries (Mermaid, rough.js, inline SVG, per `paperbanana-diagram-style-distilled.md` Section 5). Custom visualizations should be pre-rendered externally by the user and embedded as images.

---

## 7. Seminal References the Survey Cites

The AI4VIS survey highlights the following classical works as foundational. The Stylist can cite these directly when users ask for deeper justification:

| Reference | Year | Contribution |
|---|---|---|
| **Cleveland and McGill** | 1984 | Perceptual ranking of visual encoding channels through controlled human experiments. The most foundational reference for quantitative visualization effectiveness. |
| **Mackinlay (APT system)** | 1986 | Formalization of visualization effectiveness as a ranking over perceptual tasks. First automated visualization-recommendation system. |
| **Bostock et al. (D3)** | 2011 | Data-driven documents as a programming model for web visualization. Influential in establishing visualization-as-code. |
| **Satyanarayan et al. (Vega-Lite)** | 2017 | Declarative visualization grammar. Separates specification from rendering, enabling compositional authoring. |
| **Moritz et al. (Draco)** | 2019 | Constraint-based formalization of visualization design knowledge. Successor to APT using modern constraint solvers. |

### What the AI4VIS survey does NOT emphasize

The Stylist should note that the following classic visualization literature is NOT emphasized by the AI4VIS survey (even though it is foundational to the field):

- **Edward Tufte** — the data-ink ratio, chartjunk, small multiples. The canonical critique of decorative visualization.
- **Jacques Bertin** — Semiology of Graphics (1967). The pre-computer foundational work on visual variables.
- **Tamara Munzner** — Visualization Analysis and Design (2014). A modern textbook on principled visualization design.
- **Colin Ware** — Information Visualization: Perception for Design (3rd ed. 2012). Deep engagement with visual perception science.
- **Stephen Few** — Show Me the Numbers, Now You See It. Practical guidance for business and scientific data presentation.

These works are arguably MORE directly relevant to Debrief's mission than the AI4VIS survey itself, but they are not cited here because this file is a distillation of AI4VIS, not a general visualization reading list. The Stylist and visual-qa agent should treat these as "further reading" the user can pursue if they want to go deeper.

---

## 8. Using This File in Debrief

### How the Stylist cites this file

When making a recommendation during the style dialog, the Stylist should cite this file's content by paraphrasing and pointing to the underlying source. Example:

> **User:** "Why is my heatmap using jet a problem?"
>
> **Stylist:** "Jet is perceptually non-uniform — a value change from 0.5 to 0.6 does not look proportional to a change from 0.1 to 0.2, because jet's brightness curve is artificially non-monotonic. The AI4VIS survey (Wu et al. 2021, arXiv:2102.01330) cites Cleveland and McGill (1984) as the foundational perceptual-ranking literature, which ranks color hue as the least accurate channel for quantitative judgment. Perceptually uniform colormaps like viridis, magma, and plasma are engineered to match human perceptual uniformity — they preserve quantitative accuracy where jet distorts it. For these reasons, the bundled plot style guide recommends viridis, magma, or plasma for heatmaps and advises against jet."

This is the Stylist's citation voice: specific claim → academic source → practical recommendation.

### How the visual-qa agent cites this file

When emitting a Tier 2 warning, the visual-qa agent can include a one-line citation to ground the warning in literature. Example warning output:

```json
{
  "dimension": "Readability",
  "rule_id": "V-REA-05",
  "rule_name": "Low Contrast",
  "severity": "high",
  "evidence": "Body text color #C0C0C0 against background #E6F3FF — contrast ratio 1.4:1, below WCAG AA minimum of 4.5:1.",
  "rationale": "Low contrast impairs readability. Color hue is ranked as the least accurate perceptual channel per Cleveland & McGill 1984 (cited in Wu et al. 2021, AI4VIS); contrast compounds the problem by making text itself hard to resolve."
}
```

The citation is brief and concrete — it does NOT replace the primary evidence (contrast ratio measurement) but supplements it with academic grounding.

### Citation format to use

When the Stylist or visual-qa agent references this file, the citation format is:

- **Short form:** `(Wu et al. 2021, arXiv:2102.01330)`
- **With section:** `(Wu et al. 2021, §3)`
- **Citing via AI4VIS to underlying source:** `Cleveland & McGill 1984, cited in Wu et al. 2021, AI4VIS survey`

Do NOT fabricate specific page numbers or line numbers — the survey is a 20-page paper and the Explore agent reconnaissance did not capture exact page references.

---

## 9. What This File Does NOT Cover

To prevent the Stylist and visual-qa agent from over-attributing content to AI4VIS, this section explicitly lists topics that are **NOT** meaningfully covered by the survey:

- **Detailed perceptual science:** Weber's law, just-noticeable differences (JNDs), gestalt principles, pre-attentive processing. The survey acknowledges that visualization effectiveness depends on human perception but does not engage deeply with the underlying perception-science literature. For these topics, consult Ware's *Information Visualization: Perception for Design* or Wandell's *Foundations of Vision*.

- **Tufte's data-ink ratio and chartjunk discussion:** The AI4VIS survey does not elaborate on Tufte's principles. If the user asks about "chartjunk" or "data-ink ratio", cite Tufte directly (*The Visual Display of Quantitative Information*, 1983, or *Envisioning Information*, 1990) rather than AI4VIS.

- **Accessibility guidelines:** WCAG contrast requirements, colorblind-safe palettes, inclusive-design heuristics. The survey mentions accessibility in passing but provides no concrete guidance. For these, consult the W3C Web Content Accessibility Guidelines (WCAG 2.1) directly.

- **The 7 AI4VIS computational tasks in detail:** The survey's taxonomy (Transformation, Assessment, Comparison, Querying, Reasoning, Recommendation, Mining) is the paper's core organizing framework, but it is a taxonomy of RESEARCH TOPICS, not of visualization design rules. Debrief does not apply this taxonomy directly. It is useful only as context for understanding that the AI4VIS research community classifies its own work into these buckets.

- **Specific chart-type-to-data-type mappings:** The survey deliberately refrains from prescriptive "use X for data type Y" guidance. For this kind of mapping, consult the prescriptive sibling files (`paperbanana-plot-style-distilled.md` Section 3 for chart types; `paperbanana-diagram-style-distilled.md` Section 2 for diagram conventions).

**Further reading** for visualization design (not cited by AI4VIS but foundational to the field):

- Munzner, T. *Visualization Analysis and Design* (CRC Press, 2014) — systematic design methodology
- Ware, C. *Information Visualization: Perception for Design* (3rd ed., Morgan Kaufmann, 2012) — perception science
- Few, S. *Show Me the Numbers* (2nd ed., Analytics Press, 2012) — practical business/scientific presentation
- Tufte, E. *The Visual Display of Quantitative Information* (2nd ed., Graphics Press, 2001) — classical design critique
- Bertin, J. *Semiology of Graphics* (University of Wisconsin Press, 1983) — the foundational pre-computer work

---

*This file is loaded by the Debrief Stylist agent as an academic-grounding baseline per Section 22.8 and REQ-STYLE-2 step 2. It distills concepts from Wu et al. 2021 "AI4VIS: Survey on Artificial Intelligence Approaches for Data Visualization" (IEEE TVCG, arXiv:2102.01330) under fair-use academic citation. This document paraphrases rather than reproduces the paper's text; direct quotes are limited to ≤3 sentences each and are clearly delimited. For authoritative statements, consult the original paper at https://arxiv.org/abs/2102.01330. Distilled: 2026-04-11.*
