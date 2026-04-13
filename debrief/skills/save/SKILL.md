---
name: save
description: Checkpoint the current deck state and ledger to a named snapshot.
user-invocable: true
allowed-tools: Read, Write, Bash
argument-hint: "[label]"
---

# /debrief:save

Checkpoint the current deck state and create a backup snapshot.

## Trigger

Use `/debrief:save` to create a named checkpoint of the current presentation state.

## Behavior

- Writes the current `deck_state.json` to a timestamped backup under `.debrief_backups/`.
- Records the backup in the `presentations` list with the current timestamp.
- Safe to invoke at any time; does not modify slide content.

## Parameters

No parameters required. An optional description may be provided in the conversation.
