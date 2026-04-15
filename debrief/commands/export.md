# /debrief:export

Render the complete deck to a versioned PDF.

## Trigger

Use `/debrief:export` once style has been locked (`style_locked: true` in `deck_state.json`) and at least one slide has `status: "approved"`. The skill yields to routing, which guides the user through the export ordering dialog (G4.1 → G4.4) before invoking the export module.

## Behavior

- The export module (`debrief.export`, implemented at `src/debrief/export.py`) reads the `slides` array from `deck_state.json` and selects every slide whose `status` is `"approved"`. Draft and discarded slides are excluded.
- Rendering uses **Playwright** directly. Each approved slide is loaded into a single `BrowserContext` (per BC-10.2), printed to a PDF buffer, and the buffers are concatenated into one multi-page PDF. The output is the PDF; there is no intermediate format.
- Before Playwright launches, the export module invokes `python -m debrief.style_compiler style_config.json assets/style.css` to ensure the CSS is current (per REQ-EXPORT and BC-10.1). If the compiler fails, the export aborts; there is no fallback to a stale `assets/style.css`.
- The final PDF is written to `output/<presentation_folder>/deck_v{NNN}.pdf` per **REQ-EXPORT-3** (spec `stakeholder_spec.md`), where:
  - `<presentation_folder>` is the dynamically named folder for the active presentation, persisted in the `presentations` array of `deck_state.json`. Its default is computed deterministically by `routing.propose_presentation_folder_name(deck_state)` using the format `<YYYY_MM_DD>_<shortened_title>` per spec §24.10 / blueprint BC-4.7c. The user can confirm or override the default during the export ordering dialog.
  - `NNN` is a zero-padded three-digit version number that **increments within** the same `<presentation_folder>` (multiple re-exports of the same presentation produce `deck_v001.pdf`, `deck_v002.pdf`, ...).
  - **Across re-presentations** (per **REQ-LIFE-3** and spec §24.13), each new update round produces a NEW dated `<presentation_folder>` and the version counter resets to `001`. Previous deliverable folders are never modified or overwritten.
- After a successful export, an entry is appended to `output/export_log.jsonl` per REQ-EXPORT-5 (timestamp, presentation_folder, version, slide count, Playwright exit status).

## Parameters

No parameters required. Export options (slide order confirmation, separator placement, separator content, presentation folder name) are handled by the export ordering dialog at gates G4.1–G4.4. The dialog reads the proposed folder name from the prepare-time injection per BC-4.7c.

## Output location

After a successful export, the deliverable is at:

```
<project_root>/output/<YYYY_MM_DD>_<shortened_title>/deck_v{NNN}.pdf
```

Subsequent handouts and scripts for the same presentation land in the same `<presentation_folder>` per REQ-HAND-4 / REQ-SCRIPT-?.

## See also

- Spec REQ-EXPORT-1..6 — export module contract.
- Spec REQ-LIFE-3 — re-presentation lifecycle and dated-folder convention.
- Spec §24.10 — export ordering dialog.
- Spec §24.13 — re-presentation workflow.
- Blueprint BC-10.1..BC-10.8 — export module behavioral contracts.
- Blueprint BC-4.7c — deterministic deliverable-folder name proposal.
