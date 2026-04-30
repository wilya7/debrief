# /debrief:script

Generate the canonical speaker script from the deck's full memory (brief + audience + timeline + dialog + slide records).

## Trigger

Use `/debrief:script` after at least one slide is approved. The script is the canonical spoken-word narration for the deck — there is **one** script per project, written to `<project_root>/speaker_script.md`. Re-running the command regenerates the script; the prior version is automatically backed up to `.debrief/script_backups/speaker_script.<UTC ISO 8601>.md`.

The command dispatches the script-writer agent (`agents/script-writer.md`, BC-5.21) via the wrapping CLI:

```bash
python -m debrief.launcher script_writer --project-root . --trigger /debrief:script
```

## Behavior

- Reads the full memory surface: `deck_brief.md`, `output/audience.yaml` (when present), `output/timeline.jsonl`, `.debrief/dialog.jsonl`, `deck_state.json`'s slide records, and the existing `speaker_script.md` (when present, used as a co-writer baseline per BC-5.21).
- Calls the script-writer agent (`claude-sonnet-4-6`, single-turn) via the hybrid invocation pattern from BC-5.19.
- Validates the agent's output against six guardrails per **REQ-SCRIPT-WRITER-2** / **BC-3.20**:
  1. **Source traceability** — names match the roster, numerics trace to brief/dialog/slides, paper citations match `paper_attached` events.
  2. **No new positions** — prompt-only rule (no code-side check in v1).
  3. **Per-slide structure** — section count + required subsections enforced.
  4. **Length budget** — slides exceeding `(duration / slide_count) × 1.5` flagged as warnings (not blockers).
  5. **Roster-aware mentions** — name mentions require keyword overlap between roster notes and slide content.
  6. **Co-writer mode** — when prior `speaker_script.md` exists, slides with unchanged source data are checked for voice drift (Jaccard bigram similarity below 0.5 → warning).
- On guardrail failure (blockers 1, 3, 5): the failure is logged to `.debrief/script_errors.jsonl` and the prior `speaker_script.md` is retained. Exit code 0 (NEVER blocks the consultant).
- On warnings (4, 6): logged with `error_class: warning_<rule>` but do NOT block the write.
- On success: backs up the existing `speaker_script.md` to `.debrief/script_backups/`, atomically writes the new one to project root, emits a `script_done` event to `output/timeline.jsonl`.

## Preconditions

1. At least one slide must have `status == "approved"`. If none, the command logs `no_approved_slides` and exits 0 with no script written.
2. The script-writer agent-card MUST exist at `${CLAUDE_PLUGIN_ROOT}/agents/script-writer.md` (shipped with the plugin).

`/debrief:export` is no longer a precondition for `/debrief:script` — the script is intermediate prep notes, not a deliverable that depends on the export.

## Parameters

- `--project-root <path>` (optional): defaults to the current working directory.
- `--trigger <name>` (optional): one of `/debrief:script` (default, manual invocation), `deck-complete-finalization` (auto-invoked at deck-complete per the consultant's Export Transition section), or `/debrief:handout-cascade` (auto-invoked when `/debrief:handout` finds the script absent).

No interactive parameters — duration and audience details come from the brief and roster.

## Output location

```
<project_root>/speaker_script.md
```

Backups of prior versions accumulate at `<project_root>/.debrief/script_backups/speaker_script.<UTC ISO 8601>.md` (retained indefinitely; the user may delete the directory manually). The legacy versioned path `output/<presentation_folder>/script_v{NNN}.md` is RETIRED — new generations no longer produce versioned outputs.

## See also

- Spec REQ-SCRIPT-WRITER-1..4 — script-writer contract.
- Spec REQ-MEMORY-DIALOG-1, REQ-MEMORY-TIMELINE-1, REQ-CONSULT-DECK-BRIEF-1 — memory surfaces the script-writer consumes.
- Blueprint BC-3.20 — script_writer subcommand contract.
- Blueprint BC-5.21 — script-writer agent-card contract.
- Blueprint BC-11.20 — backup-before-overwrite policy.
- `agents/script-writer.md` — script-writer agent system prompt.
- `spec/script_writer_rfc.md` — architectural rationale (BUG-AUDIT-84).
