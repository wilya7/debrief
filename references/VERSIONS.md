# Bundled References — Version Tracker

This file tracks the provenance and modification history of every file in `${CLAUDE_PLUGIN_ROOT}/references/` per the Apache-2.0 attribution discipline in Section 24.39 of the Debrief stakeholder specification.

Each entry records:
- Upstream source URL and file paths
- Upstream commit (when known) or branch snapshot date
- Upstream license
- Upstream patent notices (if any)
- Debrief adaptation date and author
- A summary of Debrief-specific modifications

The file is maintained as an append-only log: when a file is updated, a new dated entry is added rather than overwriting the previous one.

---

## paperbanana-derivation-meta-prompt.md

**Status:** Generated 2026-04-11 (Pass 1 of iterative bundled-references generation task).

- **Upstream project:** PaperBanana
- **Upstream URL:** https://github.com/dwzhu-pku/PaperBanana
- **Upstream file(s) adapted:** `style_guides/generate_category_style_guide.py` (DIAGRAM_BATCH_ANALYSIS_PROMPT, PLOT_BATCH_ANALYSIS_PROMPT, DIAGRAM_FINAL_SUMMARY_PROMPT, PLOT_FINAL_SUMMARY_PROMPT)
- **Upstream commit:** main branch as of 2026-04-11 (specific commit hash to be recorded when the plugin is first packaged for release)
- **Upstream license:** Apache-2.0, © 2026 Google LLC
- **Upstream patent notice:** The PaperBanana README states that patents have been filed by Google covering the multi-agent pipeline workflows (Retriever → Planner → Stylist → Visualizer → Critic). Debrief reuses ONLY prompt-engineering patterns (documentation), not the multi-agent architecture. This reuse is consistent with Apache-2.0 permissions and does not invoke the patented workflow.
- **Debrief adaptation date:** 2026-04-11
- **Debrief adapter:** Carlo Fusco and Leonardo Restivo
- **Debrief-specific modifications:**
  - Unified PaperBanana's 2-stage batch→synthesis Gemini pipeline into a single-stage prompt suitable for the Debrief Stylist (a Claude Code subagent with direct image-reading capability, invoked once per style dialog). No batch aggregation; the Stylist reads all images in one invocation.
  - Retargeted output schema from PaperBanana's 4-section diagram/plot style guide format to Debrief's REQ-STYLE-7 `style_guide.md` 11-section schema (color rationale, typography rationale, layout grammar, diagram conventions, visual patterns catalog, anti-patterns, image placement, math rendering, presentation type guidance, symmetry/balance, rhetorical role styling).
  - Added PPTX metadata preservation rule: when `.debrief/draft/analyzer_metadata.json` is present (PPTX reference modality), exact hex codes and font family names from the metadata are preserved VERBATIM rather than eyeballed from screenshots.
  - Added conflict-handling rule: when the reference's observed style conflicts with the bundled craft-knowledge references (e.g., jet colormap), flag the conflict for user resolution at the style dialog's conflict-disclosure step per REQ-STYLE-7.
  - Adapted domain framing from PaperBanana's ML/AI-research target audience to Debrief's biomedical/neuroscience-research target audience.
- **Retained verbatim from upstream (Apache-2.0):**
  - The anti-prescriptive philosophy block (avoid rigid semantic bindings, icon-to-concept mappings, color-as-function rules).
  - The multi-option framing guidelines ("If 80%+ prevalence...", "Common choices include...", "For [purpose], observed options include...").
  - The observation-format rules ("Frame everything as OBSERVATIONS not PRESCRIPTIONS").

---

## paperbanana-diagram-style-distilled.md

**Status:** Generated 2026-04-11 (Pass 2 of iterative bundled-references generation task).

- **Upstream project:** PaperBanana
- **Upstream URL:** https://github.com/dwzhu-pku/PaperBanana
- **Upstream file adapted:** `style_guides/neurips2025_diagram_style_guide.md`
- **Upstream commit:** main branch as of 2026-04-11 (specific commit hash to be recorded when the plugin is first packaged for release)
- **Upstream license:** Apache-2.0, © 2026 Google LLC
- **Upstream patent notice:** The PaperBanana README states that patents have been filed by Google covering the multi-agent pipeline workflows. This file reuses ONLY documentation content (visual design guidance), not the multi-agent architecture.
- **Debrief adaptation date:** 2026-04-11
- **Debrief adapter:** Carlo Fusco and Leonardo Restivo
- **Debrief-specific modifications:**
  - Retargeted audience framing from NeurIPS 2025 ML/AI paper authors to biomedical/neuroscience researchers.
  - Replaced upstream Section 4 "Domain-Specific Styles" (Agent/LLM, Computer Vision/3D, Theoretical/Optimization) with four biomedical-research subdomains: Clinical & Translational, Wet-lab & Bench Science, Neuroscience & Imaging, Computational & Modeling.
  - Added a new Section 5 "Applying this guidance to Debrief's diagram libraries" with practical mappings to Mermaid (`%%{init}%%` theme variables), rough.js (roughness/bowing/fillStyle parameters), and inline SVG (CSS custom properties, `<marker>` elements, font-family rules).
  - Generalized upstream's ML-specific iconography (brain as LLM, chat bubble as prompt) to a broader set of general-purpose and biomedical-specific icons.
  - Added the 60/30/10 palette rule as a concrete heuristic.
  - Added arrowhead semantic conventions specific to biology (→ activation, ⊣ inhibition, ↔ bidirectional, ○ weak influence).
- **Retained verbatim from upstream (Apache-2.0):**
  - Section 1 aesthetic principles ("Soft Tech & Scientific Pastels", "Softened Geometry")
  - The four Zone Strategy background hex codes: `#F5F5DC` (cream), `#E6F3FF` (pale blue), `#E0F2F1` (mint), `#F3E5F5` (pale lavender)
  - Color-pairing heuristics (blue/orange, green/purple, teal/pink)
  - Line/arrow semantics (solid = forward, dashed = auxiliary, orthogonal for pipelines, curved for feedback)
  - Typography rules (sans-serif for labels, serif italic for math variables)
  - The entire Section 3 "Common Pitfalls" list (PowerPoint default look, font mixing, inconsistent dimensionality, primary backgrounds, ambiguous arrows)

## paperbanana-plot-style-distilled.md

**Status:** Generated 2026-04-11 (Pass 3 of iterative bundled-references generation task).

- **Upstream project:** PaperBanana
- **Upstream URL:** https://github.com/dwzhu-pku/PaperBanana
- **Upstream file adapted:** `style_guides/neurips2025_plot_style_guide.md`
- **Upstream commit:** main branch as of 2026-04-11 (specific commit hash to be recorded when the plugin is first packaged for release)
- **Upstream license:** Apache-2.0, © 2026 Google LLC
- **Upstream patent notice:** The PaperBanana README states that patents have been filed by Google covering the multi-agent pipeline workflows. This file reuses ONLY documentation content (data-viz style guidance), not the multi-agent architecture.
- **Debrief adaptation date:** 2026-04-11
- **Debrief adapter:** Carlo Fusco and Leonardo Restivo
- **Debrief-specific modifications:**
  - Retargeted audience framing from NeurIPS 2025 ML/AI paper authors to biomedical/neuroscience researchers.
  - Added a NEW Section 4 "Biomedical-Specific Plot Types" with 8 common biomedical plot types: Kaplan-Meier survival curves, forest plots, volcano plots, gene expression heatmaps, Manhattan plots (GWAS), ROC / precision-recall curves, dose-response curves, and box plots of patient cohorts. Each with convention, color/marker rules, required annotations, and common mistakes.
  - Added a NEW Section 6 "Applying this guidance in Debrief" clarifying the three ways plots appear in Debrief slides (embedded images, inline SVG, Mermaid pie/gantt) and an explicit rule against proposing matplotlib/plotly/seaborn as diagram libraries.
  - Dropped upstream's implicit matplotlib syntax (rcParams, figsize, alpha, linewidth) since Debrief does not call matplotlib. Aesthetic guidance retained; code-specific hooks removed.
  - Added the traffic-light avoidance note for colorblind accessibility (red vs. green).
  - Added accessibility coverage (shape coding, pattern overlays) as an explicit design principle throughout.
- **Retained verbatim from upstream (Apache-2.0):**
  - Section 1 aesthetic principles (precision, accessibility, high contrast; stark white backgrounds or Seaborn-style light gray)
  - All colormap rules: viridis (blue→yellow), magma/plasma (purple→orange), coolwarm (diverging), and the NO-jet/rainbow rule
  - Axes/grids/spines conventions (light-gray dashed/dotted grids behind data; boxed vs. open spines; subtle inward ticks)
  - Legend placement options (internal top-left/top-right vs. top-horizontal)
  - Direct-labeling preference
  - All 7 upstream Type-Specific Guidelines: Bar Charts & Histograms, Line Charts, Tree & Pie/Donut Charts, Scatter Plots, Heatmaps, Radar Charts, Miscellaneous (dot plots / lollipops)
  - Section 5 Common Pitfalls list (Excel default look, rainbow map, ambiguous lines, color over-reliance, cluttered grids) — entirely verbatim

## slide-qa-checklist.md

**Status:** Generated 2026-04-11 (Pass 4 of iterative bundled-references generation task).

- **Upstream project:** PaperBanana
- **Upstream URL:** https://github.com/dwzhu-pku/PaperBanana
- **Upstream files adapted:**
  - `prompts/diagram_eval_prompts.py` (DIAGRAM_REFERENCED_COMPARISON_{FAITHFULNESS, CONCISENESS, READABILITY, AESTHETICS}_SYSTEM_PROMPT)
  - `prompts/plot_eval_prompts.py` (PLOT_REFERENCED_COMPARISON_{FAITHFULNESS, CONCISENESS, READABILITY, AESTHETICS}_SYSTEM_PROMPT)
  - `utils/eval_toolkits.py` (`_determine_tier_outcome`, two-tier adjudication logic)
- **Upstream commit:** main branch as of 2026-04-11 (specific commit hash to be recorded when the plugin is first packaged for release)
- **Upstream license:** Apache-2.0, © 2026 Google LLC
- **Upstream patent notice:** The PaperBanana README states that patents have been filed by Google covering the multi-agent pipeline workflows. This file reuses ONLY documentation content (evaluation rubric), not the multi-agent architecture.
- **Debrief adaptation date:** 2026-04-11
- **Debrief adapter:** Carlo Fusco and Leonardo Restivo
- **Debrief-specific modifications:**
  - MAJOR RESHAPING: upstream is a COMPARISON rubric ("Model vs Human, which is better?"); Debrief evaluates a SINGLE slide with no comparison. Every rule rewritten from "which wins?" to "does this slide pass/fail?". The upstream winner enum `{Model, Human, Both are good, Both are bad}` collapses to per-dimension pass/fail in Debrief.
  - 4-dimensional framework retained as organizing structure.
  - Rule IDs changed from upstream's inline prose to Debrief-specific structured IDs: V-FAI-01..04 (Faithfulness, 4 rules), V-CON-01..03 (Conciseness, 3 rules), V-REA-01..07 (Readability, 7 rules), V-AES-01..05 (Aesthetics, 5 rules). **19 total veto rules.**
  - Added slide-specific adaptations per rule showing what a violation looks like on a Debrief slide (vs. a paper figure). E.g., "figure title rendered in image pixels" → "figure title rendered inside the embedded image instead of in slide HTML".
  - Added a new Section 8 "Mapping to Debrief's INV-* / VETO-* Taxonomy" cross-referencing the 19 checklist rules to Debrief's existing Section 16 invariants, with per-rule handling assignment (qa_checker.py vs visual-qa agent).
  - Added a new Section 7 "Output Format" specifying the JSON structure the visual-qa agent emits per REQ-QA-3, replacing PaperBanana's `winner` field with Debrief's `tier2_warnings` array structure.
  - Adapted domain framing from ML/AI paper figures to biomedical/neuroscience slides.
- **Retained verbatim from upstream (Apache-2.0):**
  - The 4 dimension names (Faithfulness, Conciseness, Readability, Aesthetics)
  - Every veto rule description — just the rule text, with comparison framing stripped but rule content preserved
  - The "default to pass" conservatism principle ("If neither subject violates any Veto Rules, the default verdict should be 'Both are good'")
  - The 2-tier adjudication ordering (Tier 1 = Faithfulness + Readability, Tier 2 = Conciseness + Aesthetics)
  - Specific threshold numbers (>15 words per bullet for V-CON-01 textual overload)
  - "Smart simplification is encouraged" principle (simpler ≠ less faithful) for V-FAI
  - "Readability is a baseline requirement, not a differentiator" principle for V-REA
  - Exception clauses verbatim: full sentences permitted for data examples (V-CON-01); subfigure labels and intentional repetition permitted (V-REA-01); intentional white space for visual hierarchy permitted (V-REA-06)

## ai4vis-survey-distilled.md

**Status:** Generated 2026-04-11 (Pass 5 of iterative bundled-references generation task).

**Attribution regime: Primary Literature (fair-use academic citation)** — distinct from the Apache-2.0 regime used for Passes 1-4. This file is NOT a code derivative; it is a paraphrase of a copyrighted IEEE TVCG paper under academic fair use.

- **Upstream source:** **AI4VIS: Survey on Artificial Intelligence Approaches for Data Visualization** by Wu, A., Wang, Y., Shu, X., Moritz, D., Cui, W., Zhang, H., Zhang, D., and Qu, H. (IEEE Transactions on Visualization and Computer Graphics, 2021).
- **arXiv ID:** 2102.01330
- **URL:** https://arxiv.org/abs/2102.01330
- **Upstream license:** Copyrighted academic paper. Used under academic fair-use for the purpose of documenting design principles in a derivative software system.
- **Distillation date:** 2026-04-11
- **Distilled by:** Carlo Fusco and Leonardo Restivo
- **Distillation approach:**
  - Paraphrase the paper's content in my own words rather than reproducing long passages.
  - Direct quotes limited to ≤3 sentences each, clearly delimited in markdown blockquotes with inline citations `(Wu et al. 2021, arXiv:2102.01330)`.
  - Exactly 5 direct quotes used (the paper's thesis statement, visual-sensitivity principle, unsystematic-design critique, aesthetic-neglect flag, and perceptual-mismatch observation).
  - Bulk of the file is paraphrase, with explicit pointers to the underlying source so downstream readers can consult the paper directly.
  - No reproduction of figures, tables, or paragraph-length extracts.
- **Debrief-specific content added:**
  - Explicit "why this file exists" framing distinguishing academic grounding (this file) from prescriptive style rules (the PaperBanana-derived sibling files).
  - Section 3 Debrief application notes for Cleveland & McGill's perceptual hierarchy — concrete examples of how the hierarchy justifies specific Debrief rules (viridis-over-jet, bar-over-pie, direct-labeling-over-legend).
  - Section 5 mapping of AI4VIS's 7 quality dimensions to Debrief's 4-dimensional visual-qa framework from `slide-qa-checklist.md`.
  - Section 6 per-anti-pattern mapping to Debrief's pipeline answers (e.g., "unsystematic design → Debrief's Consultant → Stylist → Slide Maker → visual-qa systematic pipeline").
  - Section 8 "Using This File in Debrief" with a concrete example of Stylist citation voice when a user asks "why jet?".
  - Section 9 "What This File Does NOT Cover" — explicit list of topics NOT in AI4VIS to prevent false attribution. Points to Munzner, Ware, Few, Tufte, Bertin as further reading.
- **Seminal references highlighted:** Mackinlay 1986 (APT), Cleveland & McGill 1984 (perceptual channels), Bostock et al. 2011 (D3), Satyanarayan et al. 2017 (Vega-Lite), Moritz et al. 2019 (Draco).

## preview_placeholder_content.md

**Status:** Generated 2026-04-11 (Pass 6 of iterative bundled-references generation task — FINAL PASS).

**Attribution regime: Original content** (no upstream source, no Apache-2.0 derivation, no academic citation). Fresh authoring by Carlo Fusco and Leonardo Restivo.

- **Authoring date:** 2026-04-11
- **Author:** Carlo Fusco and Leonardo Restivo
- **Purpose:** Per-archetype placeholder content catalog consumed by the Stylist during REQ-STYLE-10 live-preview generation. Contains one entry per `debrief_state.json.archetype` value, plus a `custom` fallback.
- **Schema:** Each entry has 6 fields: `title`, `subtitle`, `author`, `institution`, `content_bullets`, `data_exhibit_caption`. The schema is defined in REQ-STYLE-10 (starting at line 1144) of the Debrief stakeholder specification, with the canonical example block at lines 1186-1199 using `lab_meeting` as the worked example.
- **Archetype coverage:** All 8 archetypes from Section 14.1.1 enum: `lab_meeting`, `conference_talk`, `seminar`, `lecture`, `journal_club`, `grant_panel`, `job_talk`, `custom`.
- **Content characteristics:**
  - All names, institutions, findings, and citations are **fictional** (Jane Doe / Jamie Chen / Alex Rivera / Example Neuroscience Institute / etc.). No real people or real papers are referenced.
  - Placeholder content is biomedically grounded — it uses well-known conventions (Morris water maze, APP/PS1 mice, SOD1-G93A, tetrode recordings in CA1) that feel authentic to biomedical researchers without claiming specific studies.
  - Finding magnitudes are plausible (42% reduction, p<0.001, N=12 per group, 120 ± 15 ms) and non-specific.
  - Each archetype has a different tone appropriate for the presentation context: lab_meeting is dense/ongoing, conference_talk is polished/key-finding-first, lecture is educational/definition-first, grant_panel is vision-driven, job_talk is career-arc, etc.
  - All `content_bullets` comply with the `slide-qa-checklist.md` rule **V-CON-01 Textual Overload** (≤15 words per bullet).
- **Variation support for REGENERATE PREVIEWS:** The file includes a variation catalog with 10 alternate fictional author names and 9 alternate fictional institution names. On REGENERATE PREVIEWS, the Stylist picks a different author+institution combination while keeping the same archetype entry, so the user sees variety without changing the style under evaluation.
- **Maintenance notes:** If Debrief's archetype enum in Section 14.1.1 ever expands or changes, this file MUST be updated to add corresponding entries. Orphan archetypes (a value in `debrief_state.json` with no matching entry here) fall back to `## custom`.

---

## Task Status: COMPLETE

All 6 bundled reference files listed in Section 24.39 of the Debrief stakeholder specification have been generated. The plugin's reference corpus is now fully functional and ready to be scaffolded into `${CLAUDE_PLUGIN_ROOT}/references/` by the v3 Blueprint Author.

**Final file inventory:**

| File | Lines | Role | Attribution |
|---|---|---|---|
| `paperbanana-derivation-meta-prompt.md` | 424 | Stylist meta-prompt for reference derivation (reference-derivation mode only) | Apache-2.0 (PaperBanana) |
| `paperbanana-diagram-style-distilled.md` | 297 | Diagram craft-knowledge baseline (always loaded) | Apache-2.0 (PaperBanana) |
| `paperbanana-plot-style-distilled.md` | 334 | Plot craft-knowledge baseline (always loaded) | Apache-2.0 (PaperBanana) |
| `slide-qa-checklist.md` | 427 | Visual-qa Tier 2 judgment rubric (19 veto rules, 4 dimensions) | Apache-2.0 (PaperBanana) |
| `ai4vis-survey-distilled.md` | 294 | Academic grounding for the Stylist (always loaded) | Fair-use academic citation |
| `preview_placeholder_content.md` | ~210 | REQ-STYLE-10 preview content catalog (8 archetypes) | Original content |
| `VERSIONS.md` | (this file) | Provenance tracker | — |

**Total content: ~1,986 lines across 6 bundled reference files + ~220 lines in this version tracker.**

## Change log

- **2026-04-11 (Pass 1)** — File created. `paperbanana-derivation-meta-prompt.md` generated from PaperBanana reconnaissance (source: `style_guides/generate_category_style_guide.py`).
- **2026-04-11 (Pass 2)** — `paperbanana-diagram-style-distilled.md` generated. Source: PaperBanana's `style_guides/neurips2025_diagram_style_guide.md`. Biomedical subdomain rewrite + Debrief library section added.
- **2026-04-11 (Pass 3)** — `paperbanana-plot-style-distilled.md` generated. Source: PaperBanana's `style_guides/neurips2025_plot_style_guide.md`. Added 8 biomedical plot types (Kaplan-Meier, forest, volcano, gene heatmaps, Manhattan, ROC, dose-response, box plots) and the no-matplotlib rule.
- **2026-04-11 (Pass 4)** — `slide-qa-checklist.md` generated. Sources: PaperBanana's `prompts/diagram_eval_prompts.py`, `prompts/plot_eval_prompts.py`, `utils/eval_toolkits.py`. Major reshaping from comparison framework to single-slide judgment. 19 veto rules (V-FAI-01..04, V-CON-01..03, V-REA-01..07, V-AES-01..05).
- **2026-04-11 (Pass 5)** — `ai4vis-survey-distilled.md` generated. Source: Wu et al. 2021 "AI4VIS" (arXiv:2102.01330). Fair-use academic distillation with 5 direct quotes (≤3 sentences each). Primary Literature attribution regime.
- **2026-04-11 (Pass 6)** — `preview_placeholder_content.md` generated. Fresh authoring of per-archetype placeholder content (8 archetypes). No upstream source. **Iterative 6-pass task COMPLETE.**
