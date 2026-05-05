# Changelog

All notable changes to debrief are documented in this file.

## [Unreleased] - 2026-05-05

### Anthropic SDK declared as dependency + actionable feedback on missing-SDK (BUG-AUDIT-93)

User-reported via a child project's bug report: `/debrief:script` silently produced nothing on a fresh install. Root cause: `anthropic` Python SDK is lazy-imported at two sites in `launcher.py` (script-writer and rewriter) but was NOT declared in either `pyproject.toml` or `environment.yml`. The lazy-import correctly converted the missing-dependency state to a logged `ModuleNotFoundError` and exit 0 - but with no console output, the user saw a silent no-op. Diagnosis surfaced that the same root cause silently broke the rewriter on every default install, which means `deck_brief.md` and `output/audience.yaml` were never being synthesized.

### Added (BUG-AUDIT-93)
- `anthropic>=0.40` declared in BOTH `pyproject.toml` `[project.dependencies]` AND `environment.yml` pip section. New BC-1.18 enforces cross-file consistency.
- `bin/debrief` step 5.5 smoke test (line 114) now imports `anthropic` alongside `playwright, pptx, fitz, json_repair`. A corrupt env is now caught at bootstrap, not at the first `/debrief:script` invocation.
- Two helper functions in `launcher.py` (`_is_anthropic_module_error`, `_emit_anthropic_missing_stderr`) plus call-site logic that, when the lazy-import path raises `ModuleNotFoundError` for `anthropic`, emits a single actionable line to stderr naming the install fix.
- 15 regression tests across two new test files for the dependency declaration + the stderr/exit-code behavior.

### Changed (BUG-AUDIT-93)
- `/debrief:script` (direct CLI invocation, `trigger == "/debrief:script"`) now exits **2** when the anthropic SDK is missing, instead of silently exiting 0. Cascades from the consultant's 4-step finalization (`deck-complete-finalization`, `/debrief:handout-cascade`) keep the exit-0 contract because the next step in the cascade must continue. The rewriter (`rewrite_brief`) always exits 0 unconditionally because PreCompact must never block compaction (REQ-MEMORY-REWRITE-4) - but it now also prints the actionable stderr line so the user knows the brief did not synthesize.
- BC-3.18 and BC-3.20 amended with the new stderr + exit-code policy.

### Fixed (BUG-AUDIT-93)
- `/debrief:script` and the rewriter (PreCompact / `/debrief:refresh-brief` / `/debrief:quit`) silently failing on default installs because the anthropic SDK was never installed. The fix is purely additive - existing installs that have `anthropic` already (because the user manually `pip install`-ed it) are unaffected.

## [Unreleased] - 2026-05-03

### Auto-memory disclaimer (BUG-AUDIT-92)

User-reported during a live journal-club session: the consultant said "Hook blocked the memory write (debrief project policy)" because Claude Code's runtime auto-memory injection (pointing to `~/.claude/projects/<encoded>/memory/`) collided with debrief's project-scoped memory policy. Diagnosis: the consultant inherited Claude Code's auto-memory injection, tried to use the Write tool against an out-of-project path, and the `check-write-auth` hook correctly blocked it per BC-1.9.

### Added (BUG-AUDIT-92)
- `## Auto-Memory Disclaimer` section in `agents/consultant.md` (placed before `## Recall Discipline`). Tells the consultant to ignore Claude Code's auto-memory injection for debrief sessions, names the canonical debrief memory surfaces, references the hook block as by-design, and instructs the consultant to re-route blocked actions to the appropriate debrief CLI rather than surface them as "memory failed".
- BC-5.24 in `blueprint_contracts.md` formalising the disclaimer section structure and regression obligations.
- Troubleshooting note in `README.md` for users who hit the message in older plugin versions.

### Fixed (BUG-AUDIT-92)
- Confusing UX where the consultant surfaced an out-of-project hook block as a "memory failure" rather than re-routing to debrief's working CLIs. No data was actually lost - the dialog archive captures everything via `append_dialog_turn` and the rewriter consolidates at PreCompact.

## [Unreleased] - 2026-05-03

### Two-axis paper handling refinement (BUG-AUDIT-91)

Universalized paper acceptance after the user observed that `paper_role: none` was over-restrictive. Paper handling is now available across all archetypes; only `journal_club` and `thesis_discussion` proactively demand a paper.

### Added (BUG-AUDIT-91)
- `paper_required` boolean field on every archetype in `archetypes.json`. `true` only for `journal_club` and `thesis_discussion`; `false` everywhere else - papers are optional but accepted.
- Per-paper role override during the consultant's `## Paper Discussion`: a user can say "treat this one as background" and the consultant honors that for the specific paper, regardless of the archetype default.

### Changed (BUG-AUDIT-91)
- `paper_role: none` retired. The three archetypes that previously had it now declare positive defaults: `grant_panel` and `investor_pitch` → `background_reference`; `custom` → `concept_source`.
- `paper_analyzer` trigger is now archetype-agnostic. The consultant runs it whenever the user supplies a PDF path during discovery, regardless of `paper_role`. The role only shapes downstream slide-planning behavior.
- BC-5.23 (`blueprint_contracts.md`) split into a two-axis taxonomy: `paper_role` (behavior) + `paper_required` (proactive demand). The closed `paper_role` set drops `none`; the contract documents the universal trigger and the override mechanism.
- README "Working with Papers" table updated with a `paper_required` column and the new `none`-free archetype mapping.
- Spec REQ-CONSULT-17 re-scoped to remove the `paper_role != none` gate.

## [Unreleased] - 2026-05-03

### Paper-handling cycle (BUG-AUDIT-85 through BUG-AUDIT-90)

Coordinated audit + 7-cycle break-glass remediation of the journal-club / paper-handling pipeline. The audit identified silent data-loss bugs, a spec-vs-prompt drift, and an architectural gap that prevented papers from being used in any archetype other than journal_club. The cycles fix all three.

### Added
- `paper_role` taxonomy across all archetypes (`primary_dissection`, `primary_thematic`, `primary_document`, `concept_source`, `background_reference`, `none`) - BUG-AUDIT-90 / BC-5.23. Lab_meeting, lecture, and seminar can now use papers as an optional concept source; the user's single-figure use case (e.g., reply `2` to G1.3 to build only Figure 2) is now a first-class path.
- `## Figure Claims` block in `paper_analysis_<slug>.md` (one line per figure, format `**Figure N.** <claim>`) - BUG-AUDIT-85 / BC-12.11. Per-figure claims extracted by `paper_analyzer` are now persisted to disk; pre-fix they were silently dropped.
- `## Paper Analyzer Invocation` and `## Paper Discussion` sections in `agents/consultant.md` - BUG-AUDIT-89 / BC-5.22. The first pins deterministic plumbing (trigger, command template, sub_phase transitions, event emissions, multi-paper loop); the second describes open Socratic engagement that branches by `paper_role`.
- `## Paper-Derived Figures` section in `agents/slide-maker.md` - BUG-AUDIT-90. Documents caption styling, attribution format, single-figure rule for `concept_source`, and figure-by-figure rule for `primary_dissection`.
- Programmatic real-PDF end-to-end test (`tests/regressions/test_bug_audit_87_real_pdf_end_to_end.py`) - BUG-AUDIT-87. Generates a deterministic synthetic PDF with PyMuPDF and exercises the full pipeline; closes FINDING-IMPL-5 (mock-heavy test substrate).
- Lab-meeting single-figure smoke test in `SMOKE_TEST_PROMPT.md`.

### Changed
- `extract_figure_images` distributes images across captions on the same page in document order - BUG-AUDIT-86 / BC-12.9. Pre-fix, every caption on a shared page received `images[0][0]`, producing identical PNGs for distinct figures. The single-figure lab-meeting case was at risk on multi-figure-per-page papers.
- `extract_paper_metadata` adds page-1 heuristics for title, authors, and journal when PDF metadata is empty or producer-noise (e.g., `LaTeX with hyperref`) - BUG-AUDIT-87 / BC-12.12. Pre-fix, `journal` was always `None` and the citation line typically rendered "Figure from Unknown, YYYY, Unknown."
- `crop_whitespace` constructs sub-pixmaps via documented `fitz.Pixmap(src, irect)` constructor instead of the fragile `pixmap.set_origin(0,0).__class__(...)` chain - BUG-AUDIT-87 / BC-12.7.
- `agents/consultant.md` Step 5 `journal_club` bullet contains the literal imperative "Which paper(s) would you like to present? Give me the file path(s)." per spec line 1245 - BUG-AUDIT-88 / BC-5.11. Pre-fix, only the sub-mode question was present.
- `agents/visual-qa.md` VETO-07 detects paper-derived figures by file path under `assets/reference/papers/`, not by archetype name - BUG-AUDIT-90. Now fires for any archetype with `paper_role != none`.
- `REQ-CONSULT-17` and `REQ-CONSULT-18` re-scoped from "for journal club presentations" to "any archetype where paper_role != none" - BUG-AUDIT-90.
- Spec line 4769 (open priority question for `papers_provided=true` AND `reference_provided=true`) resolved: the two flags are independent, target disjoint state surfaces, and when both fire from one turn the consultant runs `paper_analyzer` first because paper-derived content informs the brief that informs the style dialog - BUG-AUDIT-90.

### Fixed
- Per-figure claims silently dropped from `paper_analysis_<slug>.md` despite being correctly extracted - BUG-AUDIT-85.
- Multiple captions on one page received the same image xref, producing identical figure PNGs - BUG-AUDIT-86.
- `extract_paper_metadata` always returned `journal=None`; producer-noise treated as a valid author string - BUG-AUDIT-87.
- `crop_whitespace` silently no-cropped on PyMuPDF versions where `set_origin` returns `None` - BUG-AUDIT-87.

## [1.1.0] - 2026-04-11

### Added
- Initial plugin scaffold with full multi-agent workflow
- Nine skill commands: slide, style, export, save, view, reset, quit, script, handout
- Five agent definitions: consultant, slide-maker, visual-qa, bug-diagnostic, stylist
- PreToolUse hook (check-write-auth) for write authorization enforcement
- PostToolUse hook for automated consistency review after file writes
- Eight presentation archetypes: lab_meeting, conference_talk, seminar, lecture, journal_club, grant_panel, job_talk, custom
- Bundled vendor assets: mermaid.js, rough.js, KaTeX
- Apache-2.0 license with PaperBanana attribution and patent risk disclosure
