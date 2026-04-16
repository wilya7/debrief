# /debrief:save

Checkpoint the current deck state and ledger to a named snapshot.

## Trigger

Use `/debrief:save` to create a named checkpoint you can later restore from via `/debrief:restore`.

## Behavior

- Copies `deck_state.json` and `ledger.jsonl` to `output/snapshots/<label>/` in the current project directory.
- Does NOT copy `debrief_state.json` — session state is not snapshotted.
- Does NOT modify `deck_state.json`, slide files, or any other project state. Save is a pure read-then-copy operation, safe to invoke at any time.
- The snapshot directory is created on demand via `mkdir(parents=True, exist_ok=True)`.

## Parameters

One optional positional argument: the snapshot label.

- If provided, the label is sanitized (lowercased, special characters removed, max 50 characters) per BC-11.9. If the sanitized label collides with an existing snapshot, a numeric suffix (`_2`, `_3`, ...) is appended.
- If omitted or empty, a timestamp label (`YYYYMMDD_HHMMSS`) is used.

## Output location

```
output/snapshots/<label>/deck_state.json
output/snapshots/<label>/ledger.jsonl
```
