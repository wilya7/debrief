# Debrief Script Writer Architecture — RFC

**Status:** v1.0 — architecture settled, ready for Sub-cycle A (spec/blueprint adoption)
**Date:** 2026-04-30
**Authors:** Carlo Fusco, Claude Opus 4.7
**Supersedes (on adoption):** portions of BUG-AUDIT-25 (script versioning), BUG-AUDIT-68 (handout notes-source precedence), BUG-AUDIT-77 (`speaker_script.md` non-write invariant).
**Companions:** `spec/memory_architecture_rfc.md` (BUG-AUDIT-78..83) provides the dialog archive + event timeline + audience roster + recall infrastructure this RFC consumes.

---

## 1. Problem

The current `/debrief:script` is a deterministic template renderer (`generate_script_content` in `utility_skills.py`). It produces structurally-correct script blocks but flat prose. It barely consumes the memory architecture: the only field extracted from `deck_brief.md` is `total_duration` (via `_parse_duration_from_brief`); the audience roster, event timeline, and dialog archive are ignored. Per-slide narration comes from `SlideRecord.content_summary`, which is a terse internal label, not presenter-ready prose.

Three downstream consequences:

1. **Generated scripts are flat.** The user must hand-edit `speaker_script.md` heavily before delivering. The script generator produces a skeleton, not a draft.
2. **Versioned outputs (`output/<folder>/script_v{NNN}.md`) create ambiguity.** Which version is "the script"? The deliverable that gets versioned should be the export PDF; the script is intermediate prep notes that should converge.
3. **`/debrief:handout` falls back to `content_summary` when no `speaker_script.md` is present** (BC-11.15a / BUG-AUDIT-68). A handout can be built from never-spoken text — the worst kind of leave-behind.

## 2. Goal

Replace the template renderer with a **script-writer agent** modeled on the rewriter pattern (BUG-AUDIT-80). The agent reads the full memory surface (brief, audience roster, timeline, dialog archive, slide records, optionally the existing `speaker_script.md` as a co-writer baseline) and produces presenter-ready prose. Constrain the agent with **six guardrails** that prevent drift while allowing legitimate prose-craft.

Collapse the script to a single canonical artifact (`speaker_script.md` at project root). Make `/debrief:handout` a pure packager that requires the script. Trigger script generation automatically at deck-complete as part of a finalization milestone.

## 3. Non-goals

- Replace the consultant agent or restructure dispatch.
- Build figure-by-figure paper-content awareness (e.g., journal_club archetype reading the original paper PDF for figure captions). That is a meaningful expansion deferred to BUG-AUDIT-85; the script-writer's input schema includes a forward-compatible `external_documents` slot left empty in v1.
- Build semantic source-traceability verification via a second LLM. Lightweight code-side validators (option B from the design conversation) are sufficient for v1.

## 4. Architecture overview

Same hybrid pattern as the rewriter (BUG-AUDIT-80): the agent's prompt lives in `agents/script-writer.md`; the wrapping CLI extracts the prompt, calls the Anthropic API directly, validates the output, atomically writes the result.

### 4.1 Surfaces

| Surface | Path | Role |
|---|---|---|
| **Script writer agent** | `agents/script-writer.md` | Frontmatter `model: claude-sonnet-4-6`, `maxTurns: 1`, `tools: Read`. Body encodes the six guardrails + canonical structure + co-writer protocol. |
| **Canonical speaker script** | `<project_root>/speaker_script.md` | Sole script artifact. Generator-managed with backup safety. Read by `/debrief:handout` as the only notes source. |
| **Backup directory** | `.debrief/script_backups/speaker_script.<timestamp>.md` | Prior versions copied here before each overwrite. Retained indefinitely. |
| **Failure log** | `.debrief/script_errors.jsonl` | Structured log of any script-writer failure path. Same shape as `.debrief/rewrite_errors.jsonl`. |

### 4.2 Data flow

```
slides approved + deck-complete milestone
        │
        ▼
consultant proposes finalization
        │
        ▼
/debrief:refresh-brief → /debrief:script → /debrief:export → /debrief:handout
                              │
                              ▼
        agents/script-writer.md  +  inputs:
        ├─ deck_brief.md
        ├─ output/audience.yaml
        ├─ output/timeline.jsonl
        ├─ .debrief/dialog.jsonl (relevant excerpts via recall)
        ├─ deck_state.slides (per-slide content_summary, visual_approach,
        │                     design_choices, user_assets)
        └─ existing speaker_script.md (co-writer baseline, if present)
                              │
                              ▼
        speaker_script.md (atomic write; prior version backed up)
                              │
                              ▼
        /debrief:handout → packages slide screenshots + script → PDF
```

## 5. Single canonical script

`/debrief:script` writes `speaker_script.md` at project root. Versioned `output/<folder>/script_v{NNN}.md` is **retired** — existing files in legacy projects are not migrated, but new generations stop producing them.

**Backup-before-overwrite.** Before each generation, the existing `speaker_script.md` (if present) is copied to `.debrief/script_backups/speaker_script.<UTC ISO 8601 timestamp>.md`. Backups are retained indefinitely; the user can delete `.debrief/script_backups/` manually if desired. This is the user-edit-protection mechanism: hand-tuned phrasing is never lost to a regeneration.

**BUG-AUDIT-77 invariant retraction.** `speaker_script.md` is removed from BC-11.19's "non-writable by generators" list. Update the regression test (`tests/regressions/test_bug_audit_77_generator_output_paths.py`) to remove the assertion that `utility_skills.py`'s write expressions never target `speaker_script.md`.

## 6. Script writer agent — contract

### 6.1 Inputs

The wrapping CLI builds the user-message body from these sources:

1. `deck_brief.md` — full markdown.
2. `output/audience.yaml` — parsed roster (or absent).
3. `output/timeline.jsonl` — full event timeline.
4. `.debrief/dialog.jsonl` — full dialog archive, subject to a **200K-token cap** for the entire input package. The wrapping CLI tokenizes the assembled message (a fast tiktoken-style estimate is sufficient — exact tokenization isn't required since Sonnet 4.6's window is 200K and we want comfortable headroom). If the package exceeds 200K tokens, the dialog archive is truncated from the **head** (oldest turns dropped first) until the budget is met. Brief, audience.yaml, timeline, slide records, and the existing speaker_script.md (when present) are NEVER truncated — they are bounded in size and load-bearing for the script. Only the dialog archive's tail is preserved when truncation fires.
5. `deck_state.slides` — every approved slide's slug, title, content_summary, visual_approach, design_choices, user_assets (paths only).
6. **Existing `speaker_script.md` (co-writer baseline) — when present.** Per the co-writer guardrail (§7.6), the agent uses this as preferred phrasing for sections where source content matches; new content is written fresh in a style consistent with the user's voice.
7. **`external_documents` slot — empty in v1.** Forward-compatible input shape for BUG-AUDIT-85's archetype-aware paper-content extension.

### 6.2 Output

A single markdown document — the new `speaker_script.md`. The wrapping CLI validates structure + each guardrail before atomic write.

### 6.3 Canonical structure

Per REQ-SCRIPT-3 (existing). The script has one section per approved non-backup slide, plus an optional `## Backup Slides` section after the last main slide:

```markdown
# Speaker Script

**Presentation folder:** `<folder>`
**Target duration:** <N> minutes

---

## Slide 1: <title>

**Slug:** `<slug>`

> TIME CHECK (quarter mark): At ~<M> min you should be on this slide.

### Key talking points

<presenter-ready prose>

### Transition

<transition sentence to next slide; can mention roster member by name when justified>

### Estimated speaking time

~<M.M> minutes

---

## Slide 2: ...
```

Backup-slide blocks have the same shape but are emitted under `## Backup Slides`.

## 7. The six guardrails

Each guardrail has two layers: a **system-prompt rule** the agent must follow, and a **code-side validator** the wrapping CLI runs after generation. Validation failures cause the wrapping CLI to log to `.debrief/script_errors.jsonl` and exit 0 (prior `speaker_script.md` retained — same exit-0-always pattern as the rewriter, BUG-AUDIT-80).

### 7.1 Source traceability

**Rule:** every factual claim in the script must trace to one of: the brief, the dialog archive, the timeline, the slide's `content_summary`/`visual_approach`/`design_choices`, or the audience roster. The agent may rephrase, compress, or beautify; it MUST NOT introduce new facts (new statistics, new attendee names, new claims about the data).

**Validator (lightweight, option B):**
- Names mentioned in the script must appear in `output/audience.yaml`.
- Numeric claims (matched by simple regex `\b\d+\.?\d*\s*(%|mm|cm|kg|ms|s|min|h|x|×|fold|patients|samples|n=)\b`) must appear in at least one of: brief, slides' content_summary, dialog archive (substring match).
- Paper / figure citations (matched by `paper_attached`-style references in the script) must correspond to actual `paper_attached` entries in the timeline.

### 7.2 No new positions

**Rule:** the script does not argue beyond what the user has surfaced. If the user said "this is the headline finding," foreground it. If the user did not tag importance, stay neutral. The script is a vehicle for the user's narrative — not the agent's interpretation of what the narrative should be.

**Validator:** none mechanical for v1. The system-prompt rule is the only enforcement. Future v2 could add an LLM-verifier (option C from the design conversation).

### 7.3 Per-slide structure fixed

**Rule:** one section per slide. Each section uses the canonical layout (slug, optional time-check marker, Key talking points, Transition, Estimated speaking time). Structure is non-negotiable; prose inside is free.

**Validator:**
- Section count equals `len(approved_non_backup_slides) + (1 if approved_backup_slides else 0)`.
- Each section header matches `^## Slide \d+:` (or `^## Slide \d+ \(backup\):`).
- Each section contains the four required subsections by exact heading match.

### 7.4 Length budget per slide

**Rule:** total speaking time is `total_duration` (parsed from brief). Per-slide budget is `total_duration / slide_count`. Compress or expand to fit; never silently exceed.

**Validator:** count words in each section's Key talking points + Transition body. Estimate speaking time at 150 words/minute. Slides whose estimated time exceeds the per-slide budget by more than 50% are flagged in the failure log (does NOT prevent the write — slight overrun is acceptable; gross overrun is logged for review).

### 7.5 Roster-aware mentions

**Rule:** mentions of roster members by name in the script (e.g., *"Bob, you'll especially appreciate this graph"*) are allowed only when the roster YAML's `notes` for that person plausibly relates to the slide's content. Otherwise the mention is invented context.

**Validator:** for each first-name mention in the script, find the corresponding roster entry. If the entry's `notes` field is empty or contains no keyword overlap (≥1 shared content word longer than 4 characters) with the slide's `content_summary` / `visual_approach`, the mention is flagged.

### 7.6 Co-writer mode (when prior `speaker_script.md` exists)

**Rule:** when an existing `speaker_script.md` is provided as a co-writer baseline, the agent prefers the user's phrasing **verbatim** for sections where the source content has not changed. New content (added slides, new facts the user surfaced post-hoc) is written fresh in a voice consistent with the user's existing prose.

The agent's prompt instructs it to:
- For each slide section in the existing script, compare against the latest source data.
- If unchanged: emit the user's prose verbatim.
- If changed: rewrite minimally to incorporate the new fact, preserving sentence structure where possible.
- For new slides not in the existing script: write a fresh section in the user's apparent voice (sentence length, register, vocabulary level inferred from the existing prose).

**Validator (heuristic):** for slides present in BOTH the existing script and the new generation, compute Jaccard similarity over word bigrams between the existing and new section bodies. If similarity is **below 0.5** for slides whose source data has not measurably changed since the last generation, flag the slide as a "voice drift" warning in the failure log. Does NOT prevent the write; surfaces drift for review.

**Threshold rationale.** 0.5 means at least half the user's word-pair phrasings persist when the underlying source is unchanged. A pure rewrite typically drops well below 0.5; legitimate light editing (one rephrased sentence, a tightened transition) typically stays above. The threshold is a **tunable starting point**: v2 may adjust based on observed false-positive / false-negative rates in the failure log.

"Source data measurably changed" is the gate: a slide whose `content_summary` / `visual_approach` / `design_choices` differ between generations is exempt from the drift check (the agent had legitimate reason to rewrite). The check fires only when the agent had no source justification to deviate.

## 8. `/debrief:handout` simplification

`/debrief:handout` becomes a pure packager:

- **Precondition (new):** `speaker_script.md` MUST exist. If absent, the consultant auto-cascades — runs `/debrief:script` first, then `/debrief:handout`. The user sees: *"speaker_script.md is missing — running /debrief:script first."* No hard-fail.
- **Notes source collapses to single source.** REQ-HAND-3's three-level precedence (BUG-AUDIT-68: speaker_script.md → content_summary → placeholder) is reduced to: speaker_script.md section → placeholder. `content_summary` is no longer a fallback — if a slide has no script section, the handout cell shows the placeholder per BC-11.15a (silent empty still forbidden).
- **Implementation:** `_load_speaker_script` already exists; `_resolve_handout_notes` drops the `content_summary` branch. Tests update accordingly.

## 9. Auto-finalization at deck-complete

The consultant's existing `## Export Transition` section (in `agents/consultant.md`) is amended. When the consultant detects deck-complete (last main slide approved + backup session resolved + style locked), the dispatch prompt becomes:

> *"All slides approved. Ready to finalize? I'll run, in order: (1) `/debrief:refresh-brief` to ensure the brief reflects everything we've discussed, (2) `/debrief:script` to generate the speaker script, (3) `/debrief:export` for the deck PDF, (4) `/debrief:handout` for the leave-behind. You can also pick individual deliverables if you prefer."*

User confirms → consultant runs the four in sequence via Bash. Each step has its own failure recovery (script failure logs but doesn't block subsequent steps; handout precondition triggers auto-cascade if needed).

The four individual slash commands remain manually invocable for users who want partial regeneration.

**No new slash command** (`/debrief:finalize` is not added) — the consultant orchestrates from the deck-complete prompt. This keeps orchestration in the consultant where it belongs and avoids hard-coding a sequence into a Python module.

## 10. External-document context — deferred (with v1 schema reservation)

The script-writer's input schema reserves an `external_documents` slot, **always present in v1 with an empty list**. The slot's shape is documented in v1 so BUG-AUDIT-85 doesn't have to design it from scratch and the v1 prompt can anticipate v2 inputs gracefully:

```yaml
external_documents:
  - slide_slug: "results_figure2"           # which slide this context belongs to
    paper_path: "papers/lab2024.pdf"        # source PDF (under assets/papers/ or similar)
    figure_num: 2                           # figure / table / passage number
    caption: "Figure 2. Cell viability ..." # extracted from the paper
    results_paragraph: "We observed a 35% reduction in viability after 24h ..."  # surrounding results discussion
    figure_image_path: "assets/papers/lab2024_fig2.png"  # the extracted image (may already be in slide.user_assets)
```

In v1, the input is **always `external_documents: []`** — empty list, schema-valid, ignored by the agent. The script-writer's system prompt will document this slot exists and v1 produces no entries for it; the agent doesn't mention paper-specific content in v1 even if a slide's `user_assets` references a paper image (the `user_assets` field gives image paths only, not the surrounding semantic context).

**BUG-AUDIT-85 (planned)** will populate the slot for archetypes that center external documents:

- Add a `slide.paper_reference` field on `SlideRecord` (or extend `user_assets` with structured metadata) so the slide-maker records *"this slide shows figure 2 from `papers/lab2024.pdf`."*
- Add a `paper_extract(paper_path, figure_num) -> {caption, results_paragraph}` API in `paper_analyzer.py`.
- Extend `agents/script-writer.md` with archetype-aware prompt branching: when `archetype == journal_club`, weave paper figure captions and surrounding results text into the slide's section.

Generalizable to other archetypes: thesis_discussion (thesis PDF), grant_panel (proposal PDF). The same `external_documents` slot carries the per-slide context regardless of archetype; the agent's prompt determines how to use it.

**Forward-compatibility property:** v1 → v2 transition adds entries to the list; the schema does not change shape. No breaking change to the script-writer's input contract is needed for BUG-AUDIT-85.

## 11. Failure handling

Mirror the rewriter (BUG-AUDIT-80):

- **Script-writer agent failure** (model error, malformed output, validation failure): exit 0, log to `.debrief/script_errors.jsonl` with `{timestamp, trigger, error_class, error_message}`. Prior `speaker_script.md` retained.
- **Backup write failure**: log, proceed with overwrite anyway (don't block the new write because the backup couldn't be made; the data still exists in the user's git or filesystem snapshots).
- **Atomic write failure on `speaker_script.md`**: log; prior version remains intact via the `.tmp` + rename pattern.
- **Validator warnings (co-writer voice drift; length-budget overrun > 50%):** logged but do NOT block the write. They surface in `.debrief/script_errors.jsonl` as `error_class: warning_<rule>` for review.

## 12. Spec / blueprint deltas (Sub-cycle A)

**Spec additions:**
- `BUG-AUDIT-84` Bug Catalog entry summarizing the RFC.
- `REQ-SCRIPT-WRITER-1`: agent-card ownership of `speaker_script.md`.
- `REQ-SCRIPT-WRITER-2`: six guardrails enforced by the wrapping CLI's validator.
- `REQ-SCRIPT-WRITER-3`: backup-before-overwrite semantics + `.debrief/script_backups/` retention.
- `REQ-SCRIPT-WRITER-4`: auto-finalization milestone in the consultant's Export Transition.

**Spec amendments:**
- `REQ-SCRIPT-2` (BUG-AUDIT-25 versioning): superseded — single canonical script.
- `REQ-HAND-3` (BUG-AUDIT-68 notes precedence): collapse to single source.
- `REQ-HAND-6` (BUG-AUDIT-21 handout output path): handout precondition adds *"speaker_script.md must exist; auto-cascade via /debrief:script if missing"*.

**Blueprint additions:**
- `BC-3.20`: script_writer CLI subcommand contract (mirror of BC-3.18).
- `BC-5.21`: script-writer agent-card contract (mirror of BC-5.19).
- `BC-11.15b`: handout's notes-source contract collapsed to single source (amends BC-11.15a).
- `BC-11.20`: backup-before-overwrite policy for `speaker_script.md`.

**Blueprint amendments:**
- `BC-11.6`: script versioning superseded.
- `BC-11.15a` (BUG-AUDIT-68 notes precedence): superseded by BC-11.15b.
- `BC-11.16` (handout preconditions): add `speaker_script.md` exists requirement.
- `BC-11.19` (BUG-AUDIT-77 generator output-paths table): remove `speaker_script.md` from the non-write invariant; update Generator Output Paths table.

## 13. Implementation plan — three sub-cycles

### Sub-cycle A — RFC adopted into spec/blueprint (BUG-AUDIT-84 Cycle 1)

Doc + contract only. No code.

- Append BUG-AUDIT-84 Bug Catalog entry.
- Add four normative requirements + four new BCs + amendments listed in §12.
- Update the BUG-AUDIT-77 regression test to remove the `speaker_script.md` assertion (it's no longer a non-writable file).
- Regression test for BUG-AUDIT-84 anchors (parametrized: spec contains each REQ; blueprint contains each BC).

Estimated 2-3 hours.

### Sub-cycle B — script writer agent + CLI (BUG-AUDIT-84 Cycle 2 — Phase 1)

The substantive code work.

- Ship `agents/script-writer.md`.
- Refactor `main_script_generator` to: (a) call the agent via the hybrid pattern, (b) validate output against the six guardrails, (c) backup-before-overwrite, (d) atomic write to `speaker_script.md`.
- Retire `output/<folder>/script_v{NNN}.md` outputs (function still callable but writes to project root).
- Remove versioned-output tests (BUG-AUDIT-25's `script_v*` regressions).
- Add comprehensive regression tests: agent-card extraction; validator suite (one test per guardrail); backup-before-overwrite; atomic write preserves prior on failure; co-writer mode preserves user prose; failure logging.

Estimated 4-5 hours.

### Sub-cycle C — handout simplification + auto-finalization (BUG-AUDIT-84 Cycle 2 — Phase 2)

After Sub-cycle B is solid.

- Collapse handout notes source to `speaker_script.md` only (BUG-AUDIT-68's three-level precedence reduced to two: script section → placeholder).
- Add handout precondition: `speaker_script.md` must exist.
- Amend consultant's `## Export Transition` section for auto-finalization milestone.
- Update BUG-AUDIT-68 regression tests to match the new precedence.
- Update consultant-card regression tests for the auto-finalization prompt.

Estimated 2-3 hours.

**Total estimate: 8-11 hours across three sub-cycles, each independently shippable.**

## 14. What this does NOT solve

- **Hallucination within the script.** If the script-writer agent invents a fact despite the source-traceability rule, the validator catches numeric / name / citation drift but not narrative invention (e.g., the agent writes *"this is critically important"* when the user never said so). Mitigation: the No-new-positions rule is prompt-only in v1; option C (LLM-verifier) is a v2 improvement.
- **External-document content.** Journal-club paper figures, thesis discussion sections, grant proposal language — none of these are in v1. BUG-AUDIT-85 is the planned follow-up.
- **Multi-language scripts.** v1 produces English prose. Other languages would require a per-archetype prompt language rule.
- **Re-presentation lifecycle.** REQ-LIFE-3's "new dated folder per re-presentation" applies to deck PDFs; the script collapses to single-canonical, so a re-presentation reuses or replaces the existing script (with backup). The user can manually copy `.debrief/script_backups/` if they want presentation-N's script preserved separately.

---

**End of RFC v1.0.** Architecture is settled. Ready for Sub-cycle A (BUG-AUDIT-84 — spec + blueprint adoption, no code).
