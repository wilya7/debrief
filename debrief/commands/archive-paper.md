# /debrief:archive-paper

Retroactively archive a paper PDF to `assets/reference/papers/` when the consultant's automatic trigger detection missed it.

## Trigger

Use `/debrief:archive-paper <path-to-pdf>` when:

- You provided a paper PDF earlier in the session but `assets/reference/papers/` is empty.
- `debrief_state.papers_provided` is `false` despite the deck referencing paper-derived figures.
- The consultant proposes this command after detecting paper-handling drift (per BUG-AUDIT-94).
- You want to add an additional paper after the initial briefing closed.

This command is the explicit recovery path for the deterministic paper pipeline (BC-5.11). It is idempotent: running it twice on the same PDF re-archives the file and re-emits the `paper_attached` event without corruption (the analyzer's atomic-write contract preserves prior outputs on failure and overwrites on success).

## Behavior

The command runs the full paper-analyzer pipeline plus state synchronisation:

1. Validates `<path-to-pdf>` exists and ends with `.pdf` (exits 1 with a clear stderr message otherwise).
2. Computes the paper slug from the filename per BC-12.8 (`derive_paper_slug`).
3. Runs `paper_analyzer.main_paper_analyzer()`:
   - Parses the PDF, extracts text, captions, figure images, claims, metadata.
   - Writes `.debrief/paper_analysis_<slug>.md` (captions + claims + narrative arc).
   - Writes `assets/reference/papers/<slug>/<original.pdf>` (the archived copy).
   - Writes `assets/reference/papers/<slug>/figures/fig_<N>.png` for each extractable figure.
4. Updates `debrief_state.papers_provided=true` via the canonical `python -m debrief.debrief_state update` path (BC-2.15a).
5. Appends a `paper_attached` event to `output/timeline.jsonl` (BC-2.18, payload `{"path": "<path>", "slug": "<slug>"}`).
6. Prints a one-line summary and exits 0.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success — paper archived, state updated, event emitted. |
| 1 | PDF not found or not a `.pdf` file. |
| 2 | `paper_analyzer` failed (env corruption, parse error, write failure). The underlying error is on stderr. |
| 3 | Usage error (missing `--pdf` or `--project-root`). |

## What this does NOT do

- Does NOT re-emit `figure_selected` events for previously-selected figures. If the user has already authored slides referencing the paper's figures, those slides remain unchanged. The consultant SHOULD emit `figure_selected` for each affected slide via the `## Paper Discussion` flow when the user identifies which figures map to which slides.
- Does NOT migrate paper-derived files mistakenly placed in `assets/images/` to the canonical `assets/reference/papers/<slug>/figures/` location. If you have such files, move them manually after the archive succeeds.
- Does NOT re-run the rewriter. Run `/debrief:refresh-brief` afterwards to consolidate the new `paper_attached` event into `deck_brief.md`.

## See also

- `commands/refresh-brief.md` — re-synthesize `deck_brief.md` after archiving.
- BUG-AUDIT-94 in `spec/stakeholder_spec.md` — full background on why this command exists.
- BC-5.11, BC-12.* — the paper-analyzer contracts this command exercises.
- BC-3.21 — the launcher subcommand contract (`debrief.launcher archive_paper`) that this command wraps.
