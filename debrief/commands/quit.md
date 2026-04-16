# /debrief:quit

Flush state, clean transient artifacts, print a session summary, and return.

## Trigger

Use `/debrief:quit` to finalize the session and return to the default Claude Code context.

## Behavior

- Flushes `deck_state.json` and `debrief_state.json` to disk with correct `state_hash` (BC-11.13).
- Fsyncs `ledger.jsonl` to ensure all conversation log entries are persisted.
- Conditionally retains `.debrief/draft/` only if a style dialog is in progress (BC-11.14). Otherwise, deletes the draft directory.
- Cleans transient artifacts: `.debrief/task_prompt.md` and `.debrief/gate_data.json` are deleted if present.
- Prints a session summary to stderr: phase, archetype, style_locked status, number of approved non-backup slides, last export folder (if any), and a "Run 'debrief' to resume" instruction.
- If quit is invoked during what appears to be an active red-green cycle, prints a belt-and-suspenders warning (BUG-AUDIT-24). This should never trigger in Claude Code's sequential model but documents the invariant.

## What quit does NOT do

- Does NOT call `/debrief:save` — quit flushes the current state files, it does not create a snapshot. If you want a restore point, run `/debrief:save` before quitting.
- Does NOT transition the session phase to "done" — the phase field is flushed as-is.
- Does NOT terminate the Claude Code session from the Python function. The consultant handles session closure at the conversation level after the quit function returns.

## Parameters

No parameters required. No confirmation prompt.
