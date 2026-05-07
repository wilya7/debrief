# /debrief:handout

Generate a versioned handout PDF combining slide thumbnails with speaker notes.

## Trigger

Use `/debrief:handout` once at least one slide has `status: "approved"` and `backup != True`. The consultant agent (per `agents/consultant.md` — **Alternative Dispatch Prompts** section, BC-5.15 / BUG-AUDIT-66) surfaces a conversational pre-dispatch dialog before invoking the handout module:

- When `--mode` is absent, the consultant asks which layout to use (`2up` or `4up`; default `2up`).
- When `--include-backup` is absent AND one or more approved backup slides exist, the consultant asks whether to include them (default main-only).

The handout is **independent of `/debrief:export`** (BUG-AUDIT-21). It runs on any project with approved slides; no prior export is required.

## Behavior

- **Preconditions (BC-11.16, fail-fast order):** before any Playwright work the module validates (1) `deck_state.json` exists and is readable, (2) at least one slide has `status == "approved"` AND `backup != True`, (3) `<project_root>/speaker_script.md` exists, (4) `playwright` is importable. On any failure a descriptive message is printed to stderr and the module exits code 2. The Playwright check runs last so a missing-slides run produces the right error, not a spurious environment-corruption report. **(BUG-AUDIT-103 amendment: when `speaker_script.md` is missing, the consultant orchestration layer (per `agents/consultant.md` `## Handout Generation Dispatch`, BC-5.16c) runs the BUG-AUDIT-102 four-step Task-dispatch chain to generate the script BEFORE invoking handout. The pre-103 in-subprocess auto-cascade is RETIRED — `main_handout` no longer imports `main_script_writer`. Reaching the missing-script branch in `main_handout` post-103 indicates the orchestration was bypassed (e.g., direct subprocess call); the handout exits 2 with `"speaker_script.md is missing. Run /debrief:script first, then retry /debrief:handout."`.)**
- **Slide selection:** by default, approved non-backup slides in `deck_state.json` array order. When `--include-backup` is passed, approved backup slides are appended after the main slides per BC-11.16a (BUG-AUDIT-64). Semantics match `/debrief:export`'s `--include-backup` exactly — one flag name across commands.
- **Layout:** `2up` (two slides per page, larger thumbnails, detailed notes) or `4up` (four slides per page in a 2×2 grid, compact notes). Invalid modes exit code 2.
- **Notes source per slide (BC-11.15a / BUG-AUDIT-68):** deterministic three-level precedence, applied independently per slide:
  1. `<project_root>/speaker_script.md` section matched by slug (primary, via the `**Slug:** \`<slug>\`` marker) or title (fallback, via the `## Slide N: <title>` header). Origin-agnostic — may be user-authored or a user-promoted copy of a generated `script_v{NNN}.md`. Generated scripts under `output/<folder>/script_v{NNN}.md` are NOT read by the handout.
  2. `SlideRecord.content_summary` from `deck_state.json`.
  3. Explicit placeholder `"(no notes available)"` — silent empty cells are forbidden.
- **Styling (BC-11.15 / BUG-AUDIT-21):** the handout uses its own first-class stylesheet, `handout.css`, shipped beside the handout module (workspace: `src/unit_11/handout.css`; delivered: `src/debrief/handout.css`). The stylesheet is optimized for print density and ink efficiency and is NOT derived from `style_config.json` or `assets/style.css`. Style lock is NOT required.
- **Rendering:** Playwright launches one `sync_playwright()` session per invocation and closes it in a `finally` block (BC-11.7).

## Parameters

- `--mode {2up|4up}` (required): slides-per-page layout. Default `2up` when invoked via consultant dispatch without an explicit mode.
- `--include-backup` (optional): append approved backup slides after the main slides. Default is main-only, matching `/debrief:export` (BC-11.16a / BUG-AUDIT-64).
- `--project-root <path>` (optional): defaults to the current working directory.

The consultant surfaces `--mode` and `--include-backup` conversationally before dispatch per the Dispatch Mapping table in `agents/consultant.md`. The CLI MAY be invoked directly with explicit flags; any flag supplied on the command line short-circuits the corresponding dialog.

## Output location

```
<project_root>/output/handouts/handout_v{NNN}.pdf
```

- `NNN` is a zero-padded three-digit version number derived filesystem-side (BC-11.17): the module scans `output/handouts/` for existing `handout_v*.pdf` files and picks `(max + 1)`, or `1` if the directory is empty.
- `output/handouts/` is created on first invocation via `mkdir(parents=True, exist_ok=True)`.
- The handout path is DECOUPLED from `deck_state.presentations` (BUG-AUDIT-21). The handout module does NOT consult `presentations` and does NOT mutate `deck_state.json`.

## See also

- Spec REQ-HAND-1..7 — handout contract (REQ-HAND-3 rewritten under BUG-AUDIT-68).
- Spec REQ-HAND-NOTES-1/-2 — speaker-script notes precedence.
- Spec REQ-HAND-BACKUP-1 — `--include-backup` flag.
- Blueprint BC-11.7, BC-11.8 — Playwright lifecycle and gate non-consumption.
- Blueprint BC-11.15 — handout.css.
- Blueprint BC-11.15a — notes source precedence.
- Blueprint BC-11.16 — fail-fast preconditions.
- Blueprint BC-11.16a — `--include-backup` flag.
- Blueprint BC-11.17 — decoupled output path.
- `agents/consultant.md` **Alternative Dispatch Prompts** (BC-5.15 / BUG-AUDIT-66) — consultant-side pre-dispatch dialog grammar.
- BUG-AUDIT-21 (decoupling + dedicated stylesheet), BUG-AUDIT-64 (backup flag), BUG-AUDIT-66 (dispatch dialog), BUG-AUDIT-68 (speaker-script merge), BUG-AUDIT-73 (this doc tidy).
