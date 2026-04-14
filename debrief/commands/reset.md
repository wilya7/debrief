# /debrief:reset

Delete all project data files and return the project directory to its initial empty state.

## Trigger

Use `/debrief:reset` to revert to a prior checkpoint or clear the current session.

## Behavior

- Lists available backup checkpoints from `.debrief_backups/`.
- Prompts the user to confirm which checkpoint to restore.
- On confirmation, replaces `deck_state.json` with the chosen backup.
- Does NOT delete slide HTML files; only the state manifest is reset.

## Parameters

Optional: provide a backup timestamp or name to restore directly without selection prompt.
