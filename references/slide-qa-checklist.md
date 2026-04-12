# Slide QA Checklist (PaperBanana-Distilled)

```
NOTICE
=====================================================================
This document is adapted from PaperBanana
(https://github.com/dwzhu-pku/PaperBanana),
© 2026 Google LLC, licensed under Apache License 2.0.

Source files:
  - prompts/diagram_eval_prompts.py
    (DIAGRAM_REFERENCED_COMPARISON_{FAITHFULNESS,CONCISENESS,
     READABILITY,AESTHETICS}_SYSTEM_PROMPT)
  - prompts/plot_eval_prompts.py
    (PLOT_REFERENCED_COMPARISON_{FAITHFULNESS,CONCISENESS,
     READABILITY,AESTHETICS}_SYSTEM_PROMPT)
  - utils/eval_toolkits.py (_determine_tier_outcome, two-tier adjudication)
Source commit: main branch as of 2026-04-11 (specific commit hash to
                be recorded in references/VERSIONS.md when the plugin
                is first packaged for release)

Modifications (Apache-2.0 §4(b)):

- MAJOR RESHAPING: The upstream framework is a COMPARISON rubric that
  judges "which of two versions (Model vs Human) is better?". Debrief's
  visual-qa agent evaluates a SINGLE slide with no comparison, so every
  rule has been rewritten from "which wins?" to "does this slide violate
  this rule? (pass/fail)". The upstream winner enum {Model, Human,
  Both are good, Both are bad} collapses to a per-dimension pass/fail.
  The 4-dimensional framework is retained as an organizing structure.
- Rule IDs changed from upstream's inline prose to Debrief-specific
  structured IDs: V-FAI-01..04 (Faithfulness), V-CON-01..03 (Conciseness),
  V-REA-01..07 (Readability), V-AES-01..05 (Aesthetics). 19 total rules.
- Added slide-specific adaptations per rule: what a violation looks
  like on a Debrief slide (not a paper figure). For example, the
  upstream "figure title rendered in image pixels" rule is adapted to
  "figure title rendered inside the image instead of in slide HTML".
- Added Section 8 "Mapping to Debrief's INV-* / VETO-* Taxonomy"
  (new, not from upstream) — cross-references the checklist rules to
  Debrief's existing Section 16 invariants.
- Added Section 7 "Output Format" specifying the JSON structure the
  visual-qa agent emits per REQ-QA-3, replacing PaperBanana's winner
  field with Debrief's warning structure.
- Adapted domain framing from ML/AI paper figures to biomedical/
  neuroscience slides.
- Retained VERBATIM (marked inline below): the 4 dimension names
  (Faithfulness, Conciseness, Readability, Aesthetics), every veto
  rule description (just the rule text, not the comparison framing),
  the "default to pass" conservatism principle, the two-tier
  adjudication ordering (Tier 1 = Faithfulness + Readability,
  Tier 2 = Conciseness + Aesthetics), and specific threshold numbers
  (>15 words, etc.).

Modified by:        Carlo Fusco and Leonardo Restivo
Modification date:  2026-04-11
License:            Apache-2.0 (inherited)

PATENT NOTICE — The PaperBanana README states that patents have been
filed by Google covering the multi-agent pipeline workflows. This file
reuses ONLY documentation content (evaluation rubric), not the
multi-agent architecture. See ${CLAUDE_PLUGIN_ROOT}/NOTICE for the
full patent disclosure.

Upstream URLs:
https://github.com/dwzhu-pku/PaperBanana/blob/main/prompts/diagram_eval_prompts.py
https://github.com/dwzhu-pku/PaperBanana/blob/main/prompts/plot_eval_prompts.py
https://github.com/dwzhu-pku/PaperBanana/blob/main/utils/eval_toolkits.py
=====================================================================
```

---

## Purpose

This file is the **Tier 2 judgment rubric** for the Debrief **visual-qa agent**. It is loaded as craft-knowledge context whenever the visual-qa agent evaluates a slide that has passed programmatic Tier 1 checks (from `qa_checker.py`) and is ready for visual inspection per Section 24.22.

**Who reads this file:** The **visual-qa agent** only. The Stylist does NOT load this file (the Stylist reads `paperbanana-diagram-style-distilled.md` and `paperbanana-plot-style-distilled.md` for craft-knowledge baselines; this file is for evaluation, not authoring).

**Relationship to Section 16 (Design Invariants):** This file is a **craft-knowledge baseline** for Tier 2 VLM judgments. Section 16's INV-* and VETO-* taxonomy is still authoritative — this file organizes how the agent thinks about Tier 2 judgments but does not replace or override the INV-* / VETO-* definitions. Section 8 below maps the rules in this file to the corresponding Section 16 invariants.

**Sibling files in `${CLAUDE_PLUGIN_ROOT}/references/`:**
- `paperbanana-diagram-style-distilled.md` — diagram aesthetics (Stylist baseline)
- `paperbanana-plot-style-distilled.md` — plot aesthetics (Stylist baseline, visual-qa reference)
- `ai4vis-survey-distilled.md` — academic grounding in visualization design principles
- `paperbanana-derivation-meta-prompt.md` — Stylist's reference-derivation meta-prompt

---

## 1. The Four-Dimensional Framework

The visual-qa agent evaluates each slide along **four dimensions** (from PaperBanana, verbatim):

| Dimension | Core concept |
|---|---|
| **Faithfulness** | Does the slide accurately represent the slide brief, the source material, and the user's intent? No hallucinated content, no logical contradictions, no gibberish. |
| **Conciseness** | Is the slide a high signal-to-noise visual abstraction, or is it a wall of text that the Slide Maker literal-copied from a paragraph? |
| **Readability** | Is the slide a baseline readable? Can a reader extract the core information at a glance without fighting visual noise, occlusion, or poor layout? |
| **Aesthetics** | Is the slide publication-quality polished, or does it show amateur artifacts (clip art, jarring colors, inconsistent fonts)? |

### Why four dimensions

The four dimensions provide an organizing structure for Tier 2 judgments. They are NOT orthogonal (a slide with chaotic routing might fail both Conciseness and Readability), but they are useful as a taxonomy that maps naturally to user-facing feedback: "This slide has readability issues" is more actionable than "This slide got 6.5/10 overall."

### Veto-based architecture

Each dimension has **explicit veto rules** — binary pass/fail conditions that trigger a Tier 2 warning. This replaces point-based scoring (1-5 stars) with a concrete, auditable list of failure modes. A slide either triggers a veto rule or it does not. There is no middle ground.

### "Default to Pass" conservatism

**VERBATIM PRINCIPLE (from upstream, Apache-2.0):**

> If neither subject violates any Veto Rules, the default verdict should be "Both are good," avoiding arbitrary preferences for minor stylistic variations.

**Adapted for Debrief:** If no veto rule is triggered on dimension X, the visual-qa agent MUST emit no Tier 2 warning for that dimension. Do NOT flag slides based on minor stylistic preferences, taste differences, or "it could be better" hedging. A slide that violates no veto rule is a passing slide. This is load-bearing: without this conservatism, the visual-qa agent would flag every slide, eroding user trust and desensitizing the user to real warnings.

---

## 2. Dimension A: Faithfulness

**Core concept (adapted for slides):** Technical alignment between the slide and the source material (slide brief, embedded figures, user-provided content, cited papers). A faithful slide must be factually correct, logically sound, and strictly follow the scope defined in the slide brief. It must preserve the core message without introducing fabricated content.

**Key principle (verbatim from upstream):** *Smart simplification is encouraged. A simpler slide is NOT less faithful as long as it preserves the core logic and avoids fabrication.*

### Veto Rules

**V-FAI-01 — Major Hallucination**

The slide contains content (facts, claims, data, citations, entities, relationships) that is NOT in the slide brief or the referenced source material. The Slide Maker invented content that the Consultant did not specify.

*Slide-specific example:* The slide brief says "Group A showed 30% improvement vs baseline" but the slide displays "Group A showed 45% improvement and was statistically significant (p<0.01)" — the 45% and the p-value are fabrications.

*How to detect:* Compare every numeric claim, every citation, every named entity on the slide against the brief. Any claim not traceable to the brief is a hallucination.

**V-FAI-02 — Logical Contradiction**

The slide's visual flow directly opposes the described logic in the brief. Arrows are reversed, essential steps are bypassed, or the slide shows "A causes B" when the brief says "A and B are correlated".

*Slide-specific example:* A brief describes "Treatment X increased neural activity, which led to behavioral improvement". The slide shows an arrow from "Behavioral improvement" → "Neural activity" → "Treatment X" — the causality is reversed.

*How to detect:* Trace every arrow and connector on diagram slides. Verify the directionality matches the brief.

**V-FAI-03 — Scope Violation**

The slide contains content outside the scope defined by the slide brief. The Slide Maker added material from earlier or later slides, or from a different section of the narrative arc.

*Slide-specific example:* The brief for slide 3 says "Introduce the experimental paradigm" but the slide displays results from the pilot study (which belongs to slide 5).

*How to detect:* Check that every bullet, figure, and annotation maps to a stated goal in the current slide's brief. Content not in the brief is a scope violation.

**V-FAI-04 — Gibberish Content**

The slide contains nonsensical text, garbled labels, fake mathematical notation, or broken LaTeX characters (e.g., `\frac{}{}` rendered as literal text, `$x^2$` appearing as dollar signs, Unicode replacement characters `�`).

*Slide-specific example:* A title reads "Analysis of {placeholder}" because the template wasn't substituted. Or a math expression shows `\begin{equation}\mathcal{L}` without a closing tag.

*How to detect:* Scan for `{`, `}`, `\`, `$`, unsubstituted placeholder markers, and the Unicode replacement character `�`. Cross-reference with INV-14 (math overflow) and INV-23 (math asset existence) for programmatic checks.

---

## 3. Dimension B: Conciseness

**Core concept (adapted for slides):** Visual signal-to-noise ratio. A concise slide is a high-level abstraction of the content, not a literal translation of a paragraph from the source. The slide should rely on structural shorthand (bullets, grouping, icons) and keywords rather than dense textual explanations.

### Veto Rules

**V-CON-01 — Textual Overload**

The slide contains bullets or text blocks with more than **15 words per bullet**, or full sentences rather than keyword phrases. (This 15-word threshold is preserved verbatim from upstream.)

*Exception (from upstream, verbatim):* Full sentences are permitted only for displaying data examples — verbatim quotes from the source, patient testimonials, exact measurements, direct citations. If the sentence IS the data, the rule does not apply.

*Slide-specific example:* A bullet reads "In our experiment, we first collected the behavioral data from 32 mice over a period of 14 days before performing the statistical analysis using a mixed-effects model with subject as a random factor." This is 33 words — clearly a violation. Rewrite as "N=32 mice, 14 days, mixed-effects model."

*How to detect:* Count words per bullet. Cross-reference with INV-09 (bullet count per slide).

**V-CON-02 — Literal Copying**

The slide reads like a block of paragraph text lifted verbatim from the source material. There is no visual abstraction — no keyword extraction, no bullet decomposition, no visual grouping. The Slide Maker pasted the paragraph and added bullet markers.

*Slide-specific example:* The slide contains a single paragraph-length "bullet" that is essentially the abstract of the paper rewritten with minor edits. A reader who reads the abstract learns more than a reader who reads the slide.

*How to detect:* Check whether the slide's content could be trivially copy-pasted from the source brief without rewriting. A slide that is indistinguishable from its source material is a literal copy.

**V-CON-03 — Math Dump**

The slide is cluttered with raw equations, derivations, or mathematical notation without conceptual visual structure. Mathematical content should be presented as conceptual blocks (a named equation for a named concept) with supporting visual hierarchy, not as a textbook-style derivation.

*Slide-specific example:* A single slide shows 8 consecutive equations labeling steps 1 through 8 of a derivation, with no intervening explanation or visual grouping. The slide could be any 8 equations from any paper — there's no signal about which matters.

*How to detect:* Count the number of distinct math expressions on the slide. If the slide is >50% math characters by visual area, it is a math dump. Cross-reference with INV-14 (math horizontal overflow).

---

## 4. Dimension C: Readability

**Core concept (adapted for slides, verbatim principle from upstream):** How easily a reader can extract and navigate core information. *Readability is a baseline requirement, not a differentiator. Most well-constructed slides are readable. Only severe violations of Veto Rules constitute readability failures. Minor stylistic differences should NOT be judged as readability issues.*

### Veto Rules

**V-REA-01 — Visual Noise & Extraneous Elements**

The slide contains elements that compete with the content without serving it:
- Figure titles or captions rendered inside an embedded image (when they should be in the slide HTML)
- Duplicated text labels without semantic purpose
- Watermarks, stamps, or meta-information cluttering space
- Decorative icons that don't reinforce a label

*Exception (verbatim from upstream):* Subfigure labels (a), (b), (c) and intentional repetition for demonstrating logic (e.g., repeating a block to show iteration) are permitted.

*Slide-specific example:* An embedded figure from a paper has its caption "Figure 3: Behavioral response to stimulus" rendered inside the image. The slide HTML ALSO has a caption below the image. The in-image caption is visual noise.

*How to detect:* Look for text inside embedded images that duplicates or conflicts with slide HTML text. Note that embedded figures from `assets/reference/papers/*/figures/` may contain their original captions — this is unavoidable and should be flagged as a warning for the user to address (re-crop the image or use a captionless version).

**V-REA-02 — Occlusion & Overlap**

Text overlaps with arrows, shapes, images, or other text, making elements unreadable.

*Slide-specific example:* A bullet point's text wraps into the space occupied by a diagram on the right column, with words visible through the diagram's lines. Or a figure extends beyond its container and obscures the slide title.

*How to detect:* Programmatic (INV-05 margins, INV-13 image overflow) handles the gross cases. The visual-qa agent handles subtle overlaps — text-on-text, text-on-arrow, text-on-shape — that require visual inspection.

**V-REA-03 — Chaotic Routing**

For diagram slides: spaghetti loops, excessive unnecessary arrow crossings, arrows that take winding paths when direct paths exist, or flow that cannot be traced linearly.

*Slide-specific example:* A process diagram with 5 nodes has 12 arrows between them, most of which cross each other. A reader cannot trace "which step follows which" without visually sorting the arrows.

*How to detect:* Count arrow crossings on diagram slides. If the number of crossings exceeds the number of arrows, routing is chaotic. Also check for Manhattan-style routing on conceptual diagrams (where curved Bezier routing would be cleaner) and vice versa — per `paperbanana-diagram-style-distilled.md` Section 2.C.

**V-REA-04 — Illegible Font Size**

Text is too small to read without extreme zooming, OR font sizes are wildly inconsistent (one label at 10pt next to another at 24pt for no semantic reason).

*Slide-specific example:* An embedded plot has axis labels at 6pt that are barely readable even at full-screen presentation. Or a slide uses 32pt for the title, 10pt for body bullets, and 20pt for the caption — no clear hierarchy.

*How to detect:* Cross-reference with INV-02 (font sizes) for the programmatic side. The visual-qa agent handles the subjective "can I read this at projection distance" judgment.

**V-REA-05 — Low Contrast**

Text or elements have insufficient contrast against their background — light text on light background, dark text on dark background, or medium gray on medium gray.

*Slide-specific example:* A slide uses a pale blue background and places pale gray text on it. The text is technically present but unreadable.

*How to detect:* Cross-reference with INV-04 (contrast), which is a programmatic Tier 1 check. The visual-qa agent backs this up for embedded figures where the programmatic check can't see into the image bytes.

**V-REA-06 — Inefficient Layout (Non-Rectangular Composition)**

The slide has protruding elements that create large empty margins or dead zones, unbalanced empty corners with content clusters in one region, or figures that force text to wrap in ways that waste vertical space.

*Exception (verbatim from upstream):* Intentional white space for visual hierarchy is acceptable. This rule is about AMATEUR empty space (a figure shoved to one side with nothing on the other), not deliberate minimalism.

*Slide-specific example:* A slide has a three-column layout, but the third column is empty because the figure in column 2 expanded and the text content got squished. Or a title takes up 40% of the slide height, leaving content crowded below.

*How to detect:* Cross-reference with INV-05 (margins) and INV-18 (symmetry) for the programmatic side. The visual-qa agent handles the visual-inspection judgment.

**V-REA-07 — Black Background**

The slide uses black or near-black as the background color. Academic presentations use light backgrounds (white or pale pastels per `paperbanana-diagram-style-distilled.md` Section 2.A); black backgrounds are a consumer / entertainment aesthetic unsuited to scientific content.

*Debrief-specific note:* This should never trigger after style lock because the Stylist picks the background during the style dialog. If it triggers post-lock, it indicates inline-style drift (a slide overriding the locked `style_config.json`). Cross-reference with INV-06 (no inline styles).

---

## 5. Dimension D: Aesthetics

**Core concept (adapted for slides):** Visual polish, professional maturity, design harmony. The slide should meet publication standards — refined visual hierarchy, balanced white space, consistent typography, harmonious color palette. It should feel scientific and precise, avoiding amateurish artifacts or overly simplistic clip-art styles.

### Veto Rules

**V-AES-01 — Low Quality Artifacts**

The slide contains visible background grids from diagram tools (draw.io grid lines leaking through), pixelation (a raster image blown up past its native resolution), blurry elements, or distorted shapes (stretched icons, squashed aspect ratios).

*Slide-specific example:* An embedded figure shows draw.io's editor background (gray dot grid). Or a logo pasted at 3× its original size shows visible pixels.

*How to detect:* Visual inspection. Cross-reference with INV-19 (image `src` existence), INV-20 (image aspect-ratio distortion).

**V-AES-02 — Harmonious Color Violations**

Jarring, high-saturation neon colors OR inconsistent color schemes that lack professional balance. Rainbow palettes, neon green on hot pink, or clashing saturation levels.

The **jet / rainbow colormap applied to embedded heatmaps** (or any embedded plot) is a canonical instance of a harmonious color violation — it is perceptually nonuniform and misleads readers about magnitude. See `paperbanana-plot-style-distilled.md` Section 2.A and `ai4vis-survey-distilled.md` Section 3 for the academic grounding. Jet in an embedded image is **always a Tier 2 flag** regardless of style-lock state, because the Stylist's palette enforcement cannot reach into the pixels of a raster image the user pasted into a slide.

*Debrief-specific note:* Post-lock, this rule should rarely trigger for HTML-level color drift because the Stylist defines the palette — HTML-level triggers indicate inline-style drift. The primary post-lock trigger is embedded-image colormap violations (jet in a heatmap, rainbow in a volcano plot), which bypass CSS entirely. Cross-reference with INV-06 (no inline styles) and INV-10 (permitted diagram libraries — because diagram libraries can override palette) for the HTML-side checks.

**V-AES-03 — Amateurish Styling**

The slide uses overly rounded "bubbly" shapes, "Corporate Blog" clip-art, cartoon icons, or decorative elements that lack scientific precision. This is the opposite of the "Softened Geometry" principle from `paperbanana-diagram-style-distilled.md` Section 2.B — softened corners are fine, but cartoon bubbles are amateur.

*Slide-specific example:* A slide uses a clip-art image of a gear from Microsoft Office 97 to represent "analysis". Or a flowchart uses speech-bubble shapes instead of rectangles.

*How to detect:* Visual inspection. Look for clip-art, cartoon characters, and decorative elements that would look out of place in a Nature paper.

**V-AES-04 — Inconsistent Typography**

Multiple unrelated font families on the same slide (serif headings + sans-serif body + monospace bullets), or misaligned text blocks where the Slide Maker has used different styling for parallel content.

*Debrief-specific note:* Should never trigger after style lock. Post-lock triggers indicate inline-style drift or a broken web font. Cross-reference with INV-16 (font loading) and INV-06 (no inline styles).

**V-AES-05 — Black Background**

Duplicate of V-REA-07. Both Readability and Aesthetics veto on black backgrounds — Readability because of contrast issues, Aesthetics because of aesthetic mismatch with academic publications. The rule IDs are intentionally duplicated so either dimension can trigger the warning.

---

## 6. Two-Tier Adjudication Logic

**VERBATIM from upstream** (adapted nomenclature): PaperBanana's `_determine_tier_outcome` in `utils/eval_toolkits.py` uses a two-tier adjudication where the decision flows through Tier 1 first, then Tier 2 if Tier 1 is inconclusive.

### Tier 1 (Primary): Faithfulness + Readability

A violation in either Faithfulness or Readability is **serious** — the slide has either factual problems (hallucination, contradiction) or structural problems (unreadable, occluded). Tier 1 violations should be surfaced as **high-severity warnings** at gate G3.3 and should typically trigger a `SLIDE REVISE` response from the user.

### Tier 2 (Secondary): Conciseness + Aesthetics

A violation in Conciseness or Aesthetics is **less severe** — the slide is correct and readable, just suboptimal in its density or polish. Tier 2 violations should be surfaced as **medium-severity warnings** that the user can either accept (via `SLIDE APPROVED`) or address (via `SLIDE REVISE`).

### Decision flow

The visual-qa agent evaluates all four dimensions. For each dimension:

1. Check every veto rule in that dimension.
2. If a rule is triggered, emit a warning with the rule ID, evidence, severity, and rationale.
3. If NO rule is triggered, emit no warning for that dimension (the "default to pass" principle).

After evaluating all four dimensions, the overall severity is determined by the highest-tier violation present:

- **Tier 1 violations present** → overall severity = `high`. The qa_log entry flags the slide as "Tier 2 warnings present (high severity, Tier 1 dimensions)".
- **Only Tier 2 violations present** → overall severity = `medium`. The qa_log entry flags the slide as "Tier 2 warnings present (medium severity, Tier 2 dimensions)".
- **No violations present** → no warnings emitted. The slide passes Tier 2 judgment.

This mirrors PaperBanana's "Decided at Tier X" documentation pattern, adapted for single-slide judgment instead of comparison.

### Conservative defaulting

Cross-reference Section 1's "Default to Pass" principle. If the visual-qa agent is uncertain whether a rule is triggered, it should default to NOT triggering (no warning). False positives are more harmful than false negatives here because false positives train the user to ignore warnings.

---

## 7. Output format

The visual-qa agent MUST emit its Tier 2 judgment as a JSON object with this structure (conforming to REQ-QA-3 and Section 24.22):

```json
{
  "slug": "methodology_overview",
  "timestamp": "2026-04-11T14:32:01Z",
  "passed": true,
  "veto": false,
  "checks_run": ["VETO-01", "VETO-02", "VETO-03", "VETO-04", "VETO-05", "VETO-06", "VETO-07", "INV-01", "INV-02", "INV-03", "INV-04", "INV-05", "INV-06", "INV-07", "INV-08", "INV-09"],
  "failures": [],
  "warnings": [
    {
      "invariant": "INV-09",
      "description": "Bullet 2 contains 22 words (V-CON-01 threshold: 15). Text: 'In our experiment, we first collected behavioral data from 32 mice over a period of 14 days before performing statistical analysis.'",
      "revision_instruction": "Shorten bullet 2 to under 15 words per V-CON-01 (current: 22 words). Suggest: 'N=32 mice, 14 days, mixed-effects analysis.'",
      "dimension": "Conciseness",
      "rule_id": "V-CON-01",
      "rule_name": "Textual Overload",
      "severity": "medium"
    }
  ],
  "revision_instructions": [
    "Shorten bullet 2 to under 15 words per V-CON-01 (current: 22 words). Suggest: 'N=32 mice, 14 days, mixed-effects analysis.'"
  ]
}
```

**Fields (canonical REQ-QA-3 schema):**

- `slug`, `timestamp`, `passed`, `veto`, `checks_run`, `failures`, `warnings`, `revision_instructions` — canonical qa_log.jsonl fields per REQ-QA-3 (spec lines 1333-1382). Field names MUST match exactly; all `qa_log.jsonl` writers across Debrief conform to this one schema.
- `failures` — array of sub-objects, one per Tier 1 veto or invariant trigger (this example shows an empty array). Each sub-object has `{invariant, description, revision_instruction}` plus any additional Debrief-specific properties.
- `warnings` — array of Tier 2 sub-objects from this checklist. Each warning sub-object has the REQ-QA-3 required fields `{invariant, description, revision_instruction}` PLUS the Debrief Tier 2 extras `{dimension, rule_id, rule_name, severity}` as additional properties (REQ-QA-3 rule 4 constrains the top-level `checks_run` list, not sub-object properties, so extras are permitted).
- `revision_instructions` — REQ-QA-3 requires this to be an **array of strings** (one per failure or warning that requires a user-visible fix), NOT a single string. It is the flat union of per-finding `revision_instruction` strings, presented verbatim to the user at gate G3.3.
- Note: there is no `screenshot_path` field in the canonical schema. The screenshot location is implied by REQ-QA-5's `output/screenshots/<slug>.png` convention.

**How this feeds into Debrief:** The `warnings` array is appended to the qa_log.jsonl entry for this slide. The `prepare` script for gate G3.3 reads the latest qa_log entry and embeds the warnings (and the flat `revision_instructions` array) in the slide-review prompt presented to the user.

**Severity mapping:**
- `high` = Tier 1 dimension violation (Faithfulness or Readability)
- `medium` = Tier 2 dimension violation (Conciseness or Aesthetics)

---

## 8. Mapping to Debrief's INV-* / VETO-* Taxonomy (Section 16)

This checklist is a **craft-knowledge baseline**, not a replacement for Section 16. The 19 veto rules here map to Debrief's existing invariants as follows:

| Checklist Rule | Debrief Invariant | Handled By | Notes |
|---|---|---|---|
| V-FAI-01 Major Hallucination | New Tier 2 (no programmatic equivalent) | visual-qa agent | Requires source comparison |
| V-FAI-02 Logical Contradiction | New Tier 2 | visual-qa agent | Requires source comparison |
| V-FAI-03 Scope Violation | Covered by Consultant brief enforcement | (upstream) | Before Slide Maker runs |
| V-FAI-04 Gibberish Content | INV-14 (math overflow), INV-23 (math asset existence); no programmatic VETO for narrative gibberish | qa_checker.py (INV-14, INV-23) + visual-qa (narrative gibberish) | Programmatic detection of math overflow and missing math assets; VLM-side detection of narrative gibberish, unsubstituted placeholders, broken LaTeX. Debrief has NO programmatic VETO rule for hallucinated content — Section 16's VETO-06 is specifically about slide numbering / slug meta-identifiers rendered as body content, a different concept. |
| V-CON-01 Textual Overload | INV-09 (bullet count) — partial; new Tier 2 rule for word density | visual-qa agent | Programmatic would need word counting per bullet |
| V-CON-02 Literal Copying | New Tier 2 | visual-qa agent | No programmatic analog |
| V-CON-03 Math Dump | INV-14 (math overflow) — partial; new Tier 2 for density | qa_checker.py + visual-qa | Overflow is programmatic; "too much math" is visual |
| V-REA-01 Visual Noise | New Tier 2 | visual-qa agent | Requires distinguishing in-image text from slide HTML |
| V-REA-02 Occlusion & Overlap | INV-05 (margins), INV-13 (image overflow) | qa_checker.py | Programmatic |
| V-REA-03 Chaotic Routing | New Tier 2 (diagram-specific) | visual-qa agent | Requires visual judgment |
| V-REA-04 Illegible Font Size | INV-02 (font sizes) | qa_checker.py + visual-qa | Programmatic checks absolute size; VLM checks subjective legibility |
| V-REA-05 Low Contrast | INV-04 (contrast) | qa_checker.py | Programmatic |
| V-REA-06 Inefficient Layout | INV-05 (margins), INV-18 (symmetry) | qa_checker.py + visual-qa | Programmatic margins; VLM judges "non-rectangular composition" |
| V-REA-07 Black Background | Style lock + INV-04 (contrast) | style_compiler + qa_checker.py | Should not trigger post-lock; if it does, indicates inline-style drift |
| V-AES-01 Low Quality Artifacts | INV-19 (image src), INV-20 (aspect ratio distortion) | qa_checker.py + visual-qa | Programmatic for aspect ratio; VLM for grid lines, pixelation |
| V-AES-02 Harmonious Color Violations | No programmatic INV for embedded-image colormaps (visual-qa agent judges directly); INV-06 / INV-10 catch inline-style drift in non-image contexts | visual-qa agent (embedded-image jet/rainbow detection) + qa_checker.py (INV-06, INV-10 for HTML drift) | Jet colormap in embedded heatmaps is the canonical trigger; see V-AES-02 description. HTML-level triggers should not occur post-lock. |
| V-AES-03 Amateurish Styling | New Tier 2 | visual-qa agent | Requires aesthetic judgment |
| V-AES-04 Inconsistent Typography | INV-16 (font loading), INV-06 (no inline styles) | qa_checker.py | Should not trigger post-lock |
| V-AES-05 Black Background | Same as V-REA-07 | — | Intentional duplicate |

**Most rules map to existing Section 16 invariants.** The new content this checklist brings is the **organizing framework** (4 dimensions, 2-tier adjudication) and the **"default to pass" conservatism principle** — not new invariants. When there is a conflict between this checklist and Section 16, Section 16 is authoritative.

---

## 9. "Default to Pass" Conservatism (verbatim principle)

**From upstream** (`utils/eval_toolkits.py` adjudication logic, Apache-2.0):

> If neither subject violates any Veto Rules, the default verdict should be "Both are good," avoiding arbitrary preferences for minor stylistic variations.

**Adapted for Debrief's single-slide evaluation:**

The visual-qa agent MUST adopt a conservative posture. The default outcome for every Tier 2 dimension is PASS (no warning) unless a veto rule is concretely and unambiguously triggered. Specifically:

1. **No speculative warnings.** If the agent thinks "this slide COULD be better" but no veto rule is triggered, emit no warning.
2. **No taste-based warnings.** If the agent has an aesthetic preference that differs from the slide's choices but the choices fall within acceptable options (per `paperbanana-diagram-style-distilled.md` and `paperbanana-plot-style-distilled.md`), emit no warning.
3. **Evidence-backed warnings only.** Every warning must cite concrete evidence from the slide — specific text, specific coordinates, specific measurements. "The slide feels crowded" is not evidence; "Bullet 2 has 22 words, exceeding V-CON-01 threshold of 15" is.
4. **Highest-confidence warnings first.** If the agent finds 10 potential issues, emit only the 1-3 most confident ones. Users ignore long lists.

**Why this matters:** False-positive warnings erode user trust. After two or three rounds of warnings the user disagrees with, they stop reading the warnings. This defeats the purpose of having a QA layer. The visual-qa agent's credibility depends on its ability to surface only real problems.

---

*This file is loaded by the Debrief visual-qa agent at Tier 2 judgment time per Section 24.22. It is adapted from PaperBanana (https://github.com/dwzhu-pku/PaperBanana), © 2026 Google LLC, Apache License 2.0. See `${CLAUDE_PLUGIN_ROOT}/NOTICE` for attribution details and the patent disclosure.*
