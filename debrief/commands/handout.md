# /debrief:handout

Generate a versioned, ink-efficient PDF handout from the approved slides.

## Trigger

Use `/debrief:handout` whenever you want a printable leave-behind of the current deck. The command is **independent of `/debrief:export`** — it runs on any project with at least one approved slide. You do NOT need to have rendered the projected deck first.

## Behavior

- Reads `deck_state.json` and selects every slide whose `status` is `"approved"` AND whose `backup` flag is false. Draft, needs-revision, discarded, and backup slides are excluded.
- Renders the handout via Playwright (Chromium) using the dedicated `handout.css` stylesheet shipped beside `utility_skills.py` in the plugin. The handout style is ink-efficient, grayscale-leaning, and print-optimized — it does NOT reuse the deck's `assets/style.css` and does NOT require `style_locked: true`.
- Writes the output to `output/handouts/handout_v{NNN}.pdf` in the current project directory. The version number `NNN` is derived by scanning `output/handouts/` for existing files matching `handout_v*.pdf` and picking `(max + 1)` (or `1` if the directory is empty). The `output/handouts/` directory is created automatically on first invocation.
- Does NOT mutate `deck_state.json` — versioning is filesystem-derived.
- Does NOT consume any pending gate. If called at G4.6 (handout review), the gate persists after the command returns.

## Parameters

One positional argument: the layout mode. Supported modes:

- `2up` — two slides per page with detailed notes (default if omitted).
- `4up` — four slides per page with condensed notes.

Example invocations:

```
/debrief:handout
/debrief:handout 2up
/debrief:handout 4up
```

Modes other than `2up` or `4up` are rejected with an error listing the valid values.

## Preconditions and error messages

`main_handout` validates the following before launching Chromium. Each failure exits code 2 with a descriptive message identifying exactly which prerequisite is missing:

1. **`deck_state.json` exists.** If no project is found in the current directory, the command prints an explanatory message pointing at `debrief new` and exits.
2. **At least one approved non-backup slide.** If the project exists but has no slides, only drafts, or only backup slides, the command prints a message telling you to author and approve at least one slide first.
3. **Playwright is importable.** Checked last so that missing-project / missing-slides errors are not shadowed by a misleading environment-corruption warning. If this check fails, the message points at `debrief --rebuild-env`.

## Output location

```
output/handouts/handout_v001.pdf
output/handouts/handout_v002.pdf
...
```

The handout directory is a peer of (not a child of) `output/<presentation_folder>/` — handouts are NOT bundled into the projected deck's presentation folder. If you want the two PDFs side by side, move or copy them manually.

## Relationship to /debrief:export

None. The two commands are independent. Run `/debrief:handout` whenever you want a leave-behind, whether or not you have ever run `/debrief:export`. Run `/debrief:export` when you want the projected deck PDF. You can run either one first, in any order, as often as you like.

## See also

- `commands/export.md` — generate the projected deck PDF.
- Spec `stakeholder_spec.md` REQ-HAND-4, REQ-HAND-5, REQ-HAND-6.
- Blueprint `blueprint_contracts.md` BC-11.7, BC-11.8, BC-11.15, BC-11.16, BC-11.17.
- Bug Catalog entry BUG-AUDIT-21 for the rationale behind the decoupled and fail-fast design.
