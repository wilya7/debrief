# Journal-Club PDF → Slides Pipeline Audit

**Date:** 2026-05-03
**Scope:** End-to-end audit of the workflow that takes a PDF paper for a journal club and creates slides optimized for the presentation, with extension to the lecture archetype's multi-paper concept-borrowing case.
**Status:** Audit complete; no fixes attempted (per break-glass RULE 0). Six break-glass cycles queued and sequenced.

---

## Verdict

**Works only partially.** Implementation matches its own contracts in structure and dependency boundary (94/94 unit tests pass from both layouts), but suffers from:

- Two material code bugs causing silent data loss
- A spec↔agent-prompt drift that means the consultant doesn't ask for the paper as its first question for journal_club
- Three structural gaps that block the lecture multi-paper case entirely

---

## Audit frame

Five layers were assessed:

- **Layer 0 — UI / sequencing**: when does the paper enter, how is paper_analyzer triggered, what governs sub_phase transitions
- **Layer 1 — Documentation coherence**: cross-archetype catalog of paper-as-asset; spec/blueprint/agent-prompt cross-references
- **Layer 2 — Implementation fidelity**: paper_analyzer.py vs. BC-12.* contracts
- **Layer 3 — End-to-end smoke**: NOT executed (requires interactive consultant); transitive claims documented

---

## Findings

### Layer 0 — Sequencing

**FINDING-SEQ-1 — Spec↔consultant drift on the journal-club first-question imperative** (HIGH)
- `spec/stakeholder_spec.md` line 1245 mandates: *"When archetype is journal_club, the Consultant MUST ask for paper PDFs as its first question, without waiting for a trigger: 'Which paper(s) would you like to present? Give me the file path(s).'"*
- `agents/consultant.md` Step 5 (line 93) only specifies the sub-mode question (`Single paper or topic review across multiple papers?`).
- Effect: the journal-club workflow is defined by the paper, but the consultant doesn't explicitly demand it.
- Fix layer: agent prompt or spec (decide which is authoritative).

**FINDING-SEQ-2 — paper_analyzer invocation has no explicit trigger in the agent prompt** (MEDIUM)
- BC-5.11 specifies the bash command. `agents/consultant.md` line 124 mentions "Use paper_analyzer to extract claims, figures, and citations" but has no trigger condition, no command template, no event-emission instruction, no sub_phase transition instruction.
- Effect: model judgment fills the gap → unreliable, especially after compaction.
- Fix layer: agent prompt — add a `## Paper Analyzer Invocation` section.

**FINDING-SEQ-3 — sub_phase values discovery/paper_analysis and discovery/figure_selection are listed but unspecified** (MEDIUM)
- Both values appear in the 24-element sub_phase enum but neither has entry/exit semantics, behavior description, or gate prompts.
- Effect: dead state values.
- Fix layer: agent prompt + possibly a new BC.
- **User refinement (2026-05-03):** the deterministic shell (entry/exit, command invocation, event emission) stays rule-bound. Inside the sub_phase the consultant runs an open Socratic discussion shaping narrative — paper interpretation, figure-to-narrative mapping, what to highlight or cut. Regression tests verify the structural plumbing literally; the content-discussion section is described by intent, not pinned word-for-word.

**FINDING-SEQ-4 — Multi-paper handling is unspecified beyond the sub-mode label** (MEDIUM)
- archetypes.json journal_club describes `multi_paper` as "Thematic narrative across papers (seminar-like) with comparative critique." No operational guidance on elicitation, per-paper invocation loop, cross-paper merging, cut decisions, or order.
- BC-12.8's only multi-paper rule: "each gets its own slug derived independently."
- Fix layer: spec, blueprint, agent prompt.

**FINDING-SEQ-5 — No re-entry rule for late-attached papers** (LOW)
- Spec line 1235 says analyzer runs once per paper "at the moment the user provides the paper path during discovery." Late attach (post-discovery) is undefined.
- Fix layer: spec — either forbid or define.

---

### Layer 1 — Cross-archetype coverage

**FINDING-COV-1 — Cross-archetype paper_role coverage matrix**

| Archetype | Primary asset? | Currently in archetype consultant_instructions | In consultant.md Step 5 imperative |
|---|---|---|---|
| lab_meeting | data figures | "ask for data figures early" | — |
| conference_talk | — | silent | — |
| seminar | — | silent | — |
| **lecture** | **NOT MENTIONED** | silent | — |
| journal_club | paper PDF | "The paper PDF is the primary asset" | sub-mode question only |
| grant_panel | guidelines + proposal | "Ask for grant guidelines and written proposal" | (handled in Step 5) |
| job_talk | — (papers as audience research) | "interviewer names or papers" | (handled in Step 5) |
| thesis_discussion | thesis PDF | "thesis document is a mandatory asset (PDF)" | "Please provide the thesis document (PDF)" |
| investor_pitch | pitch deck | "existing pitch deck" | (handled in Step 5) |
| custom | — | silent | — |

Only thesis_discussion has the explicit Step-5 imperative. journal_club has the sub-mode question but no imperative ask. lecture has zero paper handling. journal_club's `multi_paper` mode (papers ARE the subject) is *not* the same intent as lecture's concept-borrowing case (papers are *resources*).

**Recommendation: introduce paper_role as a first-class taxonomy.**

| paper_role | Semantics | Archetypes |
|---|---|---|
| primary_dissection | Paper IS the presentation; figure-by-figure | journal_club / single_paper |
| primary_thematic | Several papers are the comparative subject | journal_club / multi_paper |
| primary_document | Thesis/monograph/proposal — defended | thesis_discussion |
| **concept_source** | **N papers feed concepts (or even just one figure) into a presentation about something else** | **lecture, lab_meeting, seminar** |
| background_reference | Papers cited but not deeply ingested | conference_talk, job_talk |
| none | No paper handling | investor_pitch, custom |

**Note on single-figure case** (lab_meeting "I want only Figure 2"): REQ-CONSULT-18 line 1243 already specifies that G1.3 accepts "either `ALL` or a space-separated list of figure numbers." Replying `2` selects only Figure 2. Cycle 5 generalizes the gate firing condition from `archetype == journal_club` to `paper_role != none` — no new code, scope expansion only.

For `concept_source`: paper_analyzer still runs per paper and extracts figures + claims, but slide-planning differs — figures are a *resource pool*; only those that anchor a learning objective become slides; one figure may be borrowed across multiple slides; per-figure attribution mandatory.

**FINDING-COV-2 — REQ-CONSULT-17 scope is hardcoded to "for journal club presentations"** (HIGH)
- Spec line 1218: parenthetical scopes paper-analysis-on-attach to one archetype.
- This single parenthetical is the load-bearing reason the lecture path is missing.
- Fix layer: spec — re-scope to any archetype with paper_role ≠ none.

**FINDING-COV-3 — Generic "Step 2 Assets" question dilutes paper as primary asset** (MEDIUM)
- `agents/consultant.md` line 65 mixes papers with "figures, data, diagrams, photos" uniformly across archetypes.
- Fix layer: agent prompt — make Step 2 paper_role-aware.

**FINDING-COV-4 — VETO-07 scope is hardcoded to journal club** (MEDIUM)
- `agents/visual-qa.md` line 60: rule fires "for journal-club archetypes" only.
- Should fire whenever a slide has a paper-derived figure.
- Fix layer: agent prompt — switch detection from archetype to file path under `assets/reference/papers/`.

---

### Layer 2 — Implementation

**FINDING-IMPL-1 — write_paper_analysis silently drops the claims parameter** (HIGH)
- `paper_analyzer.py` lines 493–568. Function signature accepts `claims: dict[int, str]` but the body never reads it.
- Effect: REQ-CONSULT-17 step 3's per-figure claims are extracted, then discarded. The output `.debrief/paper_analysis_<slug>.md` contains only captions. REQ-CONSULT-18's "extracted claim as the key message" is impossible to satisfy.
- Fix layer: code + BC-12.10 amendment + regression test using a real fixture.

**FINDING-IMPL-2 — extract_figure_images always picks images[0][0]** (HIGH)
- `paper_analyzer.py` line 217. Comment says "first (largest or first-listed)" but code picks first only.
- Two failure modes: (1) multiple figures on one page → all get the same image; (2) multi-panel figures → only first panel saved.
- Fix layer: code — distribute images across captions or detect multi-panel; regression with multi-figure-page and multi-panel fixtures.

**FINDING-IMPL-3 — extract_paper_metadata hardcodes journal=None, falls back on PDF metadata for authors** (MEDIUM)
- `paper_analyzer.py` lines 455–490. journal never extracted; authors from PDF metadata which is often empty/wrong.
- Effect: REQ-CONSULT-18's citation line "Figure from [Authors], [Year], [Journal]" typically renders "Figure from Unknown, YYYY, Unknown."
- Fix layer: code — heuristic extraction from page-1 text.

**FINDING-IMPL-4 — crop_whitespace fitz fallback is suspicious** (LOW)
- Line 351: `pixmap.set_origin(0, 0).__class__(pixmap, rect)` — fragile API usage; wrapped in try/except so silent no-crop on failure.
- Fix layer: code — use `fitz.Pixmap(pixmap, fitz.IRect(...))` directly.

**FINDING-IMPL-5 — Test suite is mock-heavy; no end-to-end PDF fixture** (MEDIUM)
- All 94 unit_12 tests use MagicMock for fitz. Explains why FINDING-IMPL-1/2/3 weren't caught.
- Fix layer: tests — add `tests/fixtures/papers/` with at least one open-license PDF (single-figure simple, multi-figure-per-page, multi-panel) and a `tests/integration/test_paper_analyzer_real.py` running end-to-end.

---

### Layer 3 — End-to-end smoke (deferred)

Not run mechanically. Transitive claims:

- **Smoke 1 (journal_club, single paper)**: partial — figures extracted but claims missing (IMPL-1), multi-panel degraded (IMPL-2), citations "Unknown" (IMPL-3), and the consultant may or may not ask for the paper first depending on which guidance the model weighs (SEQ-1).
- **Smoke 2 (journal_club, multi-paper)**: would fail at coordination — no operational multi-paper guidance (SEQ-4).
- **Smoke 3 (lecture, multi-paper concept_source)**: would fail outright — the path does not exist as a defined workflow (COV-1, COV-2).

To convert these to observed evidence, write a non-interactive smoke harness exercising `paper_analyzer` directly on fixture PDFs and a synthetic-transcript test for consultant prompt compliance.

---

## Sequenced break-glass cycles

Six cycles, ordered to minimize re-work. Each follows the manual break-glass protocol exactly: spec → blueprint → code → execute → evaluate → regression tests → verify → delivered-repo sync → test from both layouts.

### Cycle 1 — PAPER-IMPL-1: claims data-loss in write_paper_analysis (HIGH, narrow, U12-only)
- Spec: amend REQ-CONSULT-17 step 3 to mandate claims appear in the output md.
- Blueprint: amend BC-12.10 to require claims block format.
- Code: write_paper_analysis emits a `## Figure Claims` block.
- Tests: `tests/regressions/test_paper_claims_persisted.py` using a fixture PDF.

### Cycle 2 — PAPER-IMPL-2: figure-image selection for multi-figure-per-page and multi-panel (HIGH, U12-only)
- Spec: amend REQ-CONSULT-17 step 4 for multi-panel handling.
- Blueprint: extend BC-12.9 with per-figure image selection algorithm.
- Code: extract_figure_images becomes proximity- or distribution-aware; multi-panel composite or per-panel naming.
- Tests: regressions with multi-fig-page and multi-panel fixtures.

### Cycle 6 — PAPER-IMPL-3 + IMPL-4: metadata heuristics + crop fallback + real-PDF fixtures (MEDIUM-LOW, U12-only, recommended after 1 and 2)
- Spec: amend REQ-CONSULT-17 step 1 with metadata-extraction heuristics.
- Blueprint: BC-12.x for metadata heuristics + crop sub-pixmap call.
- Code: extract_paper_metadata heuristics; crop_whitespace direct sub-pixmap construction.
- Tests: real-PDF fixture suite.

### Cycle 3 — PAPER-SEQ-1: align agent prompt to spec for journal-club imperative (MEDIUM, U5-only)
- Spec: re-affirm spec line 1245 imperative (no change).
- Blueprint: amend BC-5.11 — add precondition that `agents/consultant.md` MUST contain the literal imperative substring; regression test parses the agent card.
- Code: edit `agents/consultant.md` Step 5 journal_club entry.
- Tests: agent-card grep regression.

### Cycle 4 — PAPER-SEQ-2/3/4: deterministic invocation + open paper-discussion sub-phase + multi-paper loop (MEDIUM, U5-only)

**Deterministic shell** (regression-testable via grep):
- Trigger: paper path detected during discovery → invoke paper_analyzer (BC-5.11 verbatim command).
- Sub_phase transitions: `discovery/dialog` → `discovery/paper_analysis` after analyzer completes; → `discovery/figure_selection` after the user signals readiness; exit when figure list locked.
- Event emissions: `paper_attached` after attach, `figure_selected` after each figure goes into a slide brief.
- Multi-paper loop: per-path, with a deterministic prompt indicating which paper is in focus.

**Open-discussion core** (intent-only):
A new `## Paper Discussion` section in `agents/consultant.md` whose prose describes:
- Discuss the paper as a paper — question, argument, strengths, weaknesses.
- Help shape narrative: figure selection, ordering, cuts, missing context for the audience.
- Engage substantively — push back on framings, raise alternative interpretations, surface methodological concerns.
- For paper_role = concept_source: discussion centers on which concepts to borrow and how each maps to a learning objective.
- For paper_role = primary_dissection: discussion centers on which figures advance the critique and what the presenter will defend.

Regression tests assert the section header exists and deterministic substrings (command template, sub_phase strings, event names) are present — but do **not** pin the discussion prose word-for-word.

### Cycle 5 — PAPER-COV: cross-archetype paper_role taxonomy + lecture/lab_meeting concept_source (largest, multi-unit, run last)
Touches archetypes.json, REQ-CONSULT-17/18 scope, VETO-07 detection, possibly slide-maker.md.
- Spec: new "Paper Roles" section with the six values; REQ-CONSULT-17/18 re-scoped from "journal club" to "any paper_role ≠ none"; G1.3 gate generalized to fire on `paper_role != none`; resolve open question at spec line 4769 (priority of papers_provided + reference_provided).
- Blueprint: new BC-12.11 (paper_role-driven analyzer behavior); BC-5.11 extended with role-aware trigger; visual-qa VETO-07 generalized.
- Code:
  - archetypes.json: add `paper_role` to each archetype (journal_club: primary_dissection / primary_thematic per sub-mode; thesis_discussion: primary_document; lecture: concept_source; lab_meeting: concept_source; seminar: concept_source; conference_talk: background_reference; job_talk: background_reference; grant_panel: none; investor_pitch: none; custom: none).
  - agents/consultant.md: Step 2 paper_role-aware; Step 5 papers-as-imperative for primary_*, papers-as-resource for concept_source, papers-as-citation-pool for background_reference; G1.3 gate firing on paper_role != none.
  - agents/slide-maker.md: figure-borrowing rules for concept_source (single-figure case explicit: one figure → one slide, full attribution).
  - agents/visual-qa.md: VETO-07 detection by file path, not archetype.
- Tests: agent-card regressions per section; archetypes.json schema regression; integration test for lab_meeting + single-figure case (the user's tomorrow scenario).

### Cycle 7 — DOCS: README.md + SMOKE_TEST_PROMPT.md update pass (delivered repo only)
Run after all behavioral cycles complete. README.md and SMOKE_TEST_PROMPT.md are repo-level documents in the delivered repo (`../debrief1.0-repo/debrief/`); they are not stub-derived, so direct edits are appropriate.
- README.md: update the feature description to surface the paper_role taxonomy and the use cases enabled by it (journal-club dissection, lab-meeting single-figure borrowing, lecture multi-paper concept-borrowing); update the dependency table commentary if changed; bump version notes.
- SMOKE_TEST_PROMPT.md: add a smoke test prompt for lab_meeting + single-figure (the user's stated scenario); update the journal_club smoke to reflect the deterministic Step-5 imperative.
- CHANGELOG.md: append an entry summarizing the seven changes (Cycles 1–6) with bug-entry IDs.
- No spec or blueprint touch — pure documentation.

---

## Recommended order

**1 → 2 → 6 → 3 → 4 → 5 → 7**

Rationale: IMPL fixes (1, 2, 6) harden the underlying code path that every paper_role reuses; agent-prompt fixes (3, 4) align the journal-club path to spec while the substrate is solid; structural generalization (5) lands once the foundation is reliable; documentation (7) consolidates last to avoid six rewrites.

---

## Open considerations before opening the first bug entry

1. **Test fixture licensing**: end-to-end smokes need at least one open-license PDF (CC-BY from PLOS or eLife). Pick before Cycle 1.
2. **Open spec question (line 4769)**: priority order for `papers_provided=true` AND `reference_provided=true` — Cycle 5 is the right place to resolve it.
3. **Determinism scope reminder** (per user feedback 2026-05-03): the rule applies to structural plumbing only. Content discussion with the user about narrative/figure selection stays open. Reflected in Cycle 4's two-part shape.
