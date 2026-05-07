# /debrief:script

Generate the canonical speaker script from the deck's full memory (brief + audience + timeline + dialog + slide records).

## Trigger

Use `/debrief:script` after at least one slide is approved. The script is the canonical spoken-word narration for the deck — there is **one** script per project, written to `<project_root>/speaker_script.md`. Re-running the command regenerates the script; the prior version is automatically backed up to `.debrief/script_backups/speaker_script.<UTC ISO 8601>.md`.

## Behavior (BUG-AUDIT-102)

The consultant orchestrates a four-step Task-dispatch (per `agents/consultant.md` `## Script Generation Dispatch`):

1. **Build prompt:** `python -m debrief.launcher build_script_prompt --project-root .` — emits the structured prompt (deck brief + audience + timeline + truncated dialog + slides + existing script as co-writer baseline) to stdout.
2. **Dispatch:** `Task(subagent_type="script-writer", prompt=<captured stdout>)` — uses Claude Code's session credential. No separate `ANTHROPIC_API_KEY` required.
3. **Stage:** consultant writes the agent's markdown to `.debrief/draft/refresh_script.md` via Bash heredoc.
4. **Validate + atomic write:** `python -m debrief.launcher write_script --project-root . --trigger /debrief:script` — runs the six guardrails, performs backup-before-overwrite, atomically writes `speaker_script.md`, emits `script_done`.

- Reads the full memory surface: `deck_brief.md`, `output/audience.yaml` (when present), `output/timeline.jsonl`, `.debrief/dialog.jsonl`, `deck_state.json`'s slide records, and the existing `speaker_script.md` (when present, used as a co-writer baseline per BC-5.21).
- Validates the agent's output against six guardrails per **REQ-SCRIPT-WRITER-2** / **BC-3.20c**:
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

No user-facing parameters — duration and audience details come from the brief and roster. The consultant's dispatch invokes `build_script_prompt` and `write_script` with `--project-root .` and the appropriate `--trigger` value (one of `/debrief:script` for manual invocation, `deck-complete-finalization` for the deck-complete cascade). The legacy `/debrief:handout-cascade` trigger fires inside the handout subprocess when `speaker_script.md` is missing — that path remains on the legacy `python -m debrief.launcher script_writer` direct-SDK code path until cycle 103 cleanup decides whether to retire or refactor it.

## Output location

```
<project_root>/speaker_script.md
```

Backups of prior versions accumulate at `<project_root>/.debrief/script_backups/speaker_script.<UTC ISO 8601>.md` (retained indefinitely; the user may delete the directory manually). The legacy versioned path `output/<presentation_folder>/script_v{NNN}.md` is RETIRED — new generations no longer produce versioned outputs.

## See also

- Spec REQ-SCRIPT-WRITER-1..4 — script-writer contract.
- Spec REQ-MEMORY-DIALOG-1, REQ-MEMORY-TIMELINE-1, REQ-CONSULT-DECK-BRIEF-1 — memory surfaces the script-writer consumes.
- Blueprint BC-3.20 — script_writer subcommand contract (legacy direct-SDK path, retained for the handout-cascade trigger after BUG-AUDIT-102).
- Blueprint BC-3.20b / BC-3.20c — `build_script_prompt` + `write_script` CLIs (BUG-AUDIT-102).
- Blueprint BC-5.16b — consultant `## Script Generation Dispatch` (BUG-AUDIT-102).
- Blueprint BC-5.21 — script-writer agent-card contract (Task-dispatchable after BUG-AUDIT-102).
- Blueprint BC-11.20 — backup-before-overwrite policy.
- `agents/script-writer.md` — script-writer agent system prompt.
- `agents/consultant.md` `## Script Generation Dispatch` section — the four-step orchestration protocol.
- `spec/script_writer_rfc.md` — architectural rationale (BUG-AUDIT-84; updated by BUG-AUDIT-102).
