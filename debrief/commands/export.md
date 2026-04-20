# /debrief:export

Render the complete deck to a versioned PDF.

## Trigger

Use `/debrief:export` once style has been locked (`style_locked: true` in `deck_state.json`) and at least one slide has `status: "approved"`. The consultant agent (per `agents/consultant.md` — **Alternative Dispatch Prompts** section, BC-5.15) surfaces the backup-inclusion choice when approved backup slides exist, then dispatches the export module directly. There is no intermediate routing loop — `routing.py` was gutted in BUG-AUDIT-31; dispatch is consultant-orchestrated.

## Behavior

- The export module (`debrief.export`, implemented at `src/debrief/export.py`) reads the `slides` array from `deck_state.json` and selects every slide whose `status` is `"approved"`. Draft and discarded slides are excluded. Approved backup slides are excluded by default per BC-10.3a; passing `--include-backup` appends them at the end of the PDF.
- Rendering uses **Playwright** directly. Each approved slide is loaded into a single `BrowserContext` (per BC-10.2), printed to a PDF buffer, and the buffers are concatenated into one multi-page PDF. The output is the PDF; there is no intermediate format.
- Before Playwright launches, the export module calls `style_engine.compile_style(config_path, css_path)` to ensure the CSS is current (per REQ-EXPORT and BC-10.1). If the compiler fails, the export aborts; there is no fallback to a stale `assets/style.css`.
- The final PDF is written to `output/<presentation_folder>/deck_v{NNN}.pdf` per **REQ-EXPORT-3** (spec `stakeholder_spec.md`), where:
  - `<presentation_folder>` is the dynamically named folder for the active presentation, persisted in the `presentations` array of `deck_state.json`. On first export (when `presentations` is empty), the folder name is computed by `debrief_state.compute_presentation_folder_name(project_name)` per **REQ-EXPORT-BOOTSTRAP-1** / **BC-10.9** (BUG-AUDIT-70). The rule: if `project_name` already begins with a `YYYYMMDD`, `YYYY_MM_DD`, or `YYYY-MM-DD` date prefix, that date is normalized to `YYYY_MM_DD` form and the remainder becomes the title; today's date is NOT prepended (avoids double-dating). Otherwise, today's date is prepended and `project_name` is sanitized into the title portion via the algorithm in spec §24.10.1 / BC-2.16 (`sanitize_identifier` with `max_length=40`). The user MAY rename the folder in `deck_state.json` before the next export if they prefer a different label; re-exports of the same presentation reuse the existing folder name from the record.
  - `NNN` is a zero-padded three-digit version number that **increments within** the same `<presentation_folder>` (multiple re-exports of the same presentation produce `deck_v001.pdf`, `deck_v002.pdf`, ...). Versioning is filesystem-derived per BC-10.4 (scan the directory, take `max + 1`).
  - **Across re-presentations** (per **REQ-LIFE-3** and spec §24.13), each new update round produces a NEW dated `<presentation_folder>` and the version counter resets to `001`. Previous deliverable folders are never modified or overwritten.
- After a successful export, an entry is appended to `output/export_log.jsonl` per REQ-EXPORT-5 (timestamp, presentation_folder, version, slide count, Playwright exit status).

## Parameters

- `--include-backup` (optional): include approved backup slides at the end of the PDF. Default is main-only, matching `/debrief:present` and `/debrief:view`. The consultant surfaces this choice conversationally before dispatch when approved backup slides exist (see `agents/consultant.md` — **Alternative Dispatch Prompts** / BC-5.15).

No other parameters. There is no interactive export-ordering dialog at the CLI — slide order is the order in the `slides` array of `deck_state.json`. Closing-slide and separator behavior are configured in `deck_state.json` (`closing_slide` field; `PresentationRecord.separator_position` / `separator_content`) and consumed by `build_page_list` per BC-10.3.

## Output location

After a successful export, the deliverable is at:

```
<project_root>/output/<YYYY_MM_DD>_<title>/deck_v{NNN}.pdf
```

Subsequent handouts and scripts for the same presentation have **decoupled** output paths per BUG-AUDIT-21 (handout) and BUG-AUDIT-25 (script):

- Handouts → `output/handouts/handout_v{NNN}.pdf` (independent of `presentations`).
- Scripts → `output/<presentation_folder>/script_v{NNN}.md` (same folder as the export).

## See also

- Spec REQ-EXPORT-1..6 — export module contract.
- Spec REQ-EXPORT-BOOTSTRAP-1 — deterministic folder-name rule (BUG-AUDIT-70).
- Spec REQ-LIFE-3 — re-presentation lifecycle and dated-folder convention.
- Spec §24.10 — export ordering (array order = PDF order).
- Spec §24.13 — re-presentation workflow.
- Blueprint BC-10.1..BC-10.9 — export module behavioral contracts.
- Blueprint BC-10.9 — folder-name bootstrap rule (date detection + today fallback).
- `agents/consultant.md` **Alternative Dispatch Prompts** — consultant-side pre-dispatch dialog.
