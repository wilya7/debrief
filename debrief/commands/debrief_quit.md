# /debrief:quit

Save state, clean up transient artifacts, and exit the session cleanly.

## Trigger

Use `/debrief:quit` to finalize the session, save state, and exit the debrief workflow.

## Behavior

- Performs a final automatic save (equivalent to `/debrief:save`).
- Summarizes the session: slides approved, exports generated, groups completed.
- Transitions the session phase to `done` in `debrief_state.json`.
- Hands control back to the default Claude Code context.

## Parameters

No parameters required.
