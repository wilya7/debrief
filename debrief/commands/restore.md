# /debrief:restore

Restore the project to a previously saved snapshot.

## Trigger

Use `/debrief:restore` to roll back your deck content to a known-good state. This command was previously named `/debrief:reset` and has been reimplemented as backup-restore in BUG-AUDIT-22. The old hard-delete behavior is permanently removed.

## Behavior

**List mode** (`/debrief:restore` with no argument):
- Scans `output/snapshots/` for valid snapshot directories (each must contain `deck_state.json`).
- Prints one line per snapshot with label and contents.
- If no snapshots exist, prints guidance to run `/debrief:save` first.
- Does not modify any files.

**Restore mode** (`/debrief:restore <label>`):
1. Validates that `output/snapshots/<label>/deck_state.json` exists.
2. Auto-saves current state to `output/snapshots/pre_restore_<timestamp>/` as a safety net. Every restore is reversible — if you regret it, restore again from the auto-save.
3. Overwrites `deck_state.json` from the snapshot.
4. If the snapshot contains `ledger.jsonl`, overwrites that too. Otherwise leaves the current ledger untouched.
5. Sweeps orphan slide HTML: any `slides/*.html` file whose slug is not in the restored `deck_state.json` is deleted. Swept filenames are logged.
6. Appends a restore_log entry to `ledger.jsonl` recording what happened.
7. Prints confirmation with source snapshot, swept slides, and auto-save label.

## What restore does NOT touch

- `CLAUDE.md` — never modified.
- `debrief_state.json` — session state is independent of deck content.
- `style_config.json`, `style_guide.md` — style decisions survive the restore.
- `deck_brief.md` — the presentation brief survives.
- `.debrief/` — scratch area survives (including any in-progress drafts).
- `assets/` — vendor libraries and compiled CSS survive.

Restore rolls back **deck content state** only (the slide manifest and optionally the conversation ledger). Everything else stays as-is.

## Parameters

One optional positional argument: the snapshot label. Omit to list available snapshots.

```
/debrief:restore              → list available snapshots
/debrief:restore my_save_1    → restore from 'my_save_1'
```

## Preconditions

- **List mode**: none. Runs even without a project.
- **Restore mode**: `deck_state.json` must exist (the auto-save needs something to save). The named snapshot must exist and contain `deck_state.json`.

On any precondition failure, the command prints a descriptive message and exits code 2. No raw tracebacks.

## See also

- `commands/save.md` — create a snapshot to restore from later.
- Spec `stakeholder_spec.md` REQ-RESTORE-1 through REQ-RESTORE-4.
- Blueprint `blueprint_contracts.md` BC-11.11, BC-11.12.
- Bug Catalog entry BUG-AUDIT-22.
